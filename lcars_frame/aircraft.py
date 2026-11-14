"""
aircraft.py

Reads the aircraft seen by your ADS-B receiver (the dump1090 that feeds
Flightradar24) on a background thread, and keeps the ones within RADIUS_NM
nautical miles as an AircraftData (see aircraft_data.py). This is the only place that
knows dump1090's names and formats: they are translated into the
provider-independent classes here. No drawing code - display them however you like.

Usage:

    fetcher = AircraftFetcher().start()
    ...
    data = fetcher.get_aircraft()           # an AircraftData (read-only)
    error = fetcher.get_error()             # str, or None if the last fetch worked
    for plane in data.aircraft:             # nearest first
        print(plane.callsign, plane.altitude_ft, plane.distance_nm)

    data.last_success                       # Unix time of the last good fetch, or None

HOW THE DISTANCE IS WORKED OUT
    aircraft.json doesn't say where your receiver is, so the distance and
    bearing of each aircraft are calculated from HOME_LAT and HOME_LON (from my_settings.py).

TRAILS
    The fetcher remembers where each aircraft it has listed has been for the last
    TRAIL_SECONDS seconds. Each Aircraft has them in its trail (oldest first), as
    (bearing, distance) pairs from your receiver, so they can be drawn as a line
    behind it. A position is only remembered when it has changed.

An aircraft is left out if it has not sent a position, if its position is
more than MAX_POSITION_AGE_SECS seconds old, if it is more than RADIUS_NM
nautical miles away, if it is on the ground, or if it is not below
MAX_ALTITUDE_FT feet. An aircraft that has not sent its altitude is left out
too, as it can't be checked.

If the receiver can't be reached, get_aircraft() has no aircraft (until a
fetch works again) and get_error() gives the reason, rather than anything being
raised. Each failure is also printed, with its traceback.
"""

import json
import math
import operator
import sys
import threading
import time
import traceback
import urllib.request

from .aircraft_data import Aircraft, AircraftData, looks_military, service_for_callsign

from settings import AIRCRAFT_URL, HOME_LAT, HOME_LON     # your receiver, from my_settings.py

# Its settings are in settings.py (next to lcars.py)
from settings import (
    AIRCRAFT_POLL_SECONDS as POLL_SECONDS,
    AIRCRAFT_RADIUS_NM as RADIUS_NM,
    AIRCRAFT_SERVICE_RADIUS_NM as SERVICE_RADIUS_NM,
    AIRCRAFT_MAX_ALTITUDE_FT as MAX_ALTITUDE_FT,
    AIRCRAFT_MAX_POSITION_AGE_SECS as MAX_POSITION_AGE_SECS,
    AIRCRAFT_TRAIL_SECONDS as TRAIL_SECONDS,
)
EARTH_RADIUS_NM = 3440.065


# From the first latitude/longitude point to the second (degrees), returns
# (distance in nautical miles, bearing in degrees true: 0 = north, 90 = east,
# range 0 to 359.9).
def distance_and_bearing(lat1, lon1, lat2, lon2):
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_lambda = math.radians(lon2 - lon1)

    sin_phi1 = math.sin(phi1)
    cos_phi1 = math.cos(phi1)
    sin_phi2 = math.sin(phi2)
    cos_phi2 = math.cos(phi2)

    # distance (haversine formula)
    a = math.sin((phi2 - phi1) / 2) ** 2 + cos_phi1 * cos_phi2 * math.sin(d_lambda / 2) ** 2
    distance = 2 * EARTH_RADIUS_NM * math.asin(math.sqrt(a))

    # bearing
    x = math.sin(d_lambda) * cos_phi2
    y = cos_phi1 * sin_phi2 - sin_phi1 * cos_phi2 * math.cos(d_lambda)
    bearing = math.degrees(math.atan2(x, y)) % 360

    return distance, bearing


# Download a web page and decode the JSON in it.
def get_json(url, timeout=5):
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


# An exception as text that is never blank: 'URLError: <urlopen error ...>'.
# Some exceptions have no message at all, so the type name always goes first.
def error_text(exc):
    message = str(exc)
    if message:
        return f"{type(exc).__name__}: {message}"
    return type(exc).__name__


# Print a failed fetch with its full traceback. Both go to stderr, which is
# never buffered, so they appear straight away wherever the program is run from.
def report_failure(what, exc):
    print(f"{what} failed: {error_text(exc)}", file=sys.stderr, flush=True)
    traceback.print_exception(type(exc), exc, exc.__traceback__)


# Note where an aircraft is, in the history that is kept of every aircraft (icao ->
# list of (time, bearing, distance), oldest first). Returns its trail: the
# (bearing, distance) of where it had been before, oldest first. A position the
# same as the last one is not added again.
def remember_position(history, icao, now, bearing, distance):
    points = history.setdefault(icao, [])

    if points and points[-1][1:] == (bearing, distance):
        return tuple(point[1:] for point in points[:-1])

    trail = tuple(point[1:] for point in points)
    points.append((now, bearing, distance))
    return trail


# Forget the positions that are more than TRAIL_SECONDS old, and the aircraft that
# then have none left
def prune_history(history, now):
    for icao in list(history):
        history[icao] = [point for point in history[icao] if point[0] > now - TRAIL_SECONDS]

        if not history[icao]:
            del history[icao]


# The aircraft's callsign. The receiver leaves it out when it hasn't decoded one lately (they
# come in separate, rarer messages), so the last one seen is kept in callsigns (icao ->
# (time, callsign)) and given instead, for up to TRAIL_SECONDS after it was last seen.
def remember_callsign(callsigns, icao, now, callsign):
    if callsign:
        callsigns[icao] = (now, callsign)
        return callsign

    seen, last = callsigns.get(icao, (0, None))
    if now - seen > TRAIL_SECONDS:
        callsigns.pop(icao, None)
        return None

    return last


# Forget the callsigns last seen more than TRAIL_SECONDS ago
def prune_callsigns(callsigns, now):
    for icao in list(callsigns):
        if callsigns[icao][0] <= now - TRAIL_SECONDS:
            del callsigns[icao]


class AircraftFetcher:
    """
    Polls the receiver for aircraft on its own daemon thread. Never blocks the
    caller, and on a failed poll keeps the last good list rather than clearing it.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._data = AircraftData()         # the latest good data; replaced, never changed
        self._error = None                  # str, or None if the last poll worked
        self._history = {}                  # icao -> [(time, bearing, distance)], only used by the poll
        self._callsigns = {}                # icao -> (time, callsign) last seen, only used by the poll
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._poll_once()  # first fetch synchronously so data is ready
        self._thread.start()
        return self

    def stop(self):
        self._stop.set()

    def _run(self):
        while not self._stop.wait(POLL_SECONDS):
            self._poll_once()

    def _poll_once(self):
        try:
            aircraft = []
            items = get_json(AIRCRAFT_URL).get("aircraft", [])

            now = time.time()
            prune_history(self._history, now)
            prune_callsigns(self._callsigns, now)

            for item in items:
                # dump1090-fa and dump1090-mutability name some values differently,
                # so each of those is looked up under both names.
                lat = item.get("lat")
                lon = item.get("lon")
                if lat is None or lon is None:
                    continue
                if item.get("seen_pos", item.get("seen", 0)) > MAX_POSITION_AGE_SECS:
                    continue

                altitude = item.get("alt_baro", item.get("altitude"))
                if altitude is None or altitude == "ground" or altitude >= MAX_ALTITUDE_FT:
                    continue

                distance, bearing = distance_and_bearing(HOME_LAT, HOME_LON, lat, lon)
                if distance > RADIUS_NM:
                    continue

                plane = Aircraft()
                plane.icao = item.get("hex", "").upper()
                plane.callsign = remember_callsign(self._callsigns, plane.icao, now,
                                                   item.get("flight", "").strip() or None)
                plane.on_ground = False         # the ones on the ground were left out above
                plane.altitude_ft = altitude
                plane.speed_kt = item.get("gs", item.get("speed"))
                plane.track_deg = item.get("track")
                plane.vertical_rate_fpm = item.get("baro_rate", item.get("vert_rate"))
                plane.latitude = lat
                plane.longitude = lon
                plane.distance_nm = distance
                plane.bearing_deg = bearing
                plane.squawk = item.get("squawk")
                plane.category = item.get("category")
                # readsb marks military aircraft itself (bit 0 of dbFlags); dump1090 doesn't
                plane.military = bool(item.get("dbFlags", 0) & 1) or looks_military(plane.icao, plane.callsign)
                plane.service = service_for_callsign(plane.callsign)
                plane.trail = remember_position(self._history, plane.icao, now, bearing, distance)
                aircraft.append(plane)

            aircraft.sort(key=operator.attrgetter("distance_nm"))

            # A new AircraftData each time, which is never changed once it is
            # published, so readers can hold on to the one they were given.
            data = AircraftData()
            data.load(aircraft)                 # also sets last_success
            with self._lock:
                self._data = data
                self._error = None
        except Exception as exc:
            # Receiver switched off or unreachable, bad JSON - keep the last good list.
            report_failure("Aircraft update", exc)
            with self._lock:
                self._error = error_text(exc)

    def get_aircraft(self):
        """Return the latest AircraftData. It is never changed after this (the next
        poll makes a new one), so treat it as read-only. It has no aircraft and a
        last_success of None until a poll has worked."""
        with self._lock:
            return self._data

    def get_error(self):
        """Return the error from the latest poll, or None if it worked."""
        with self._lock:
            return self._error
            
            