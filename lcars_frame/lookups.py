"""
lookups.py

Looks up extra details of an aircraft that the receiver can't tell us. dump1090
only knows what the aircraft itself transmits, which doesn't include where it is
flying from and to, or what type of aircraft it is. They are looked up on the web
from the free adsbdb.com service, on a background thread. This is the only place
that knows that service's names and formats; they are translated into the classes
in aircraft_data.py.

Two lookups are set up here:

    ROUTE_URL   by callsign,   e.g. 'RYR1715'  ->  a Route         (make_route)
    MODEL_URL   by hex address, e.g. '4CA7B1'  ->  an AircraftType  (make_model)

Usage:

    routes = Lookup(ROUTE_URL, make_route).start()
    ...
    route = routes.get("RYR1715")       # a Route, or None
    if route is not None:
        print(route.airline, route.origin_name, route.destination_name)

get() never waits. The first time a key is asked for it returns None and the
lookup is done in the background, so ask again on a later screen update. None
also means that the service has nothing for that key (a private flight, say) or
that the lookup failed. The answers are kept in a Cache: a good one for
FOUND_EXPIRY_SECS, a missing one for MISSING_EXPIRY_SECS, after which it is
tried again.

A failed lookup is printed with its traceback; nothing is raised to the caller.

The service limits how many lookups it will answer in a while, and answers HTTP 429
(Too Many Requests) past that. So the lookups are spaced out (LOOKUP_PAUSE_SECS), and
after a 429 all of them (routes and models alike) stop for a while, longer each time
it happens again, rather than keep asking and stay blocked.
"""

import json
import queue
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from . import cache
from .aircraft import error_text, report_failure
from .aircraft_data import AircraftType, Route

ROUTE_URL = "https://api.adsbdb.com/v0/callsign/"
MODEL_URL = "https://api.adsbdb.com/v0/aircraft/"
FOUND_EXPIRY_SECS = 6 * 60 * 60     # a good answer is looked up again after this long
MISSING_EXPIRY_SECS = 5 * 60        # ...and a missing one, after this long
TIMEOUT_SECS = 10
RETRY_EXPIRY_SECS = 30               # a lookup that couldn't reach the service is tried again after this long
HOME_AIRPORT = "MAN"                # routes are only shown for flights to or from this airport (its code)
LOOKUP_PAUSE_SECS = 0.5             # each lookup thread waits this long between lookups
BACKOFF_SECS = 60                   # after a 429, all lookups stop for this long (or as long as the service says)...
BACKOFF_MAX_SECS = 30 * 60          # ...doubling each time it happens again, up to this, until a lookup works


# Shared by both lookups, as they use the same service and it counts them together
_backoff_lock = threading.Lock()
_backoff_until = 0                  # time.monotonic() when lookups may start again
_backoff_secs = BACKOFF_SECS        # how long the next pause will be


# Wait until the service is to be asked again (at once, unless it has said too many requests)
def wait_for_backoff():
    with _backoff_lock:
        wait = _backoff_until - time.monotonic()

    if wait > 0:
        time.sleep(wait)


# The service has said too many requests: stop all lookups for a while. Retry-After is how
# long it asks for, in seconds, if it says. The pause doubles each time, up to BACKOFF_MAX_SECS.
def start_backoff(retry_after):
    global _backoff_until, _backoff_secs

    with _backoff_lock:
        if time.monotonic() < _backoff_until:
            return                  # the other lookup has already started one

        try:
            secs = max(float(retry_after), _backoff_secs)
        except (TypeError, ValueError):
            secs = _backoff_secs

        _backoff_until = time.monotonic() + secs
        _backoff_secs = min(_backoff_secs * 2, BACKOFF_MAX_SECS)

    print(f"Lookups: adsbdb says too many requests, pausing them for {secs:.0f}s", flush=True)


# A lookup has worked, so the next pause (if there is one) starts short again
def reset_backoff():
    global _backoff_secs

    with _backoff_lock:
        _backoff_secs = BACKOFF_SECS


# Download the answer for one key and decode the JSON in it. Returns None if the
# service says it has no such key (it answers 404 for those).
def get_lookup_json(url, key):
    request = urllib.request.Request(url + urllib.parse.quote(key), headers={"User-Agent": "lcars-display"})

    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECS) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise


# The code of an airport from the service's description of it, or None
def airport_code(airport):
    if not airport:
        return None

    return airport.get("iata_code") or airport.get("icao_code") or None


# The name of the place an airport serves ('Prague'), or failing that the airport's
# own name, or failing that its code
def airport_name(airport):
    if not airport:
        return None

    return airport.get("municipality") or airport.get("name") or airport_code(airport)


# The "response" part of the service's answer for a key, e.g. the dictionary
# under "flightroute", or None if there is nothing there. (For a key it doesn't
# know it may answer with 404, or with a text instead of a dictionary.)
def get_answer(data, name):
    response = data.get("response") if data else None

    if isinstance(response, dict):
        return response.get(name) or None

    return None


# Turn the service's answer for a callsign into a Route, or None if it has none
def make_route(data):
    flightroute = get_answer(data, "flightroute")
    if not flightroute:
        return None

    airline = flightroute.get("airline")
    origin = flightroute.get("origin")
    destination = flightroute.get("destination")

    route = Route()
    route.airline = airline.get("name") if isinstance(airline, dict) else None
    route.origin = airport_code(origin)
    route.origin_name = airport_name(origin)
    route.destination = airport_code(destination)
    route.destination_name = airport_name(destination)
    return route


# The route if the flight is going to or from the airport with this code (e.g. 'MAN'),
# otherwise None. The service gives one route per callsign, which is often wrong for
# the aircraft actually overhead, so only the routes of flights at our own airport are
# shown: those are the ones that are likely to be right.
def route_at_airport(route, code):
    if route is None:
        return None

    if code in (route.origin, route.destination):
        return route

    return None


# Turn the service's answer for a hex address into an AircraftType, or None if it has none
def make_model(data):
    aircraft = get_answer(data, "aircraft")
    if not aircraft:
        return None

    manufacturer = aircraft.get("manufacturer")

    # Airliners have a full type like '737-8AS'. Others (home built, say) only a
    # short code, so give that with the maker: 'Vans RV7'.
    model = aircraft.get("type")
    if not model:
        model = " ".join(part for part in (manufacturer, aircraft.get("icao_type")) if part) or None

    result = AircraftType()
    result.manufacturer = manufacturer
    result.model = model
    result.registration = aircraft.get("registration")
    return result


class Lookup:
    """
    Looks things up one at a time on its own daemon thread, and remembers the answers.
    make_result is a function that turns the service's answer into a result (or None).
    """

    def __init__(self, url, make_result):
        self._url = url
        self._make_result = make_result
        self._cache = cache.Cache()
        self._lock = threading.Lock()
        self._pending = set()               # keys waiting to be looked up
        self._queue = queue.Queue()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()
        return self

    def stop(self):
        self._queue.put(None)

    def _run(self):
        while True:
            key = self._queue.get()
            if key is None:
                break

            wait_for_backoff()
            self._lookup(key)
            time.sleep(LOOKUP_PAUSE_SECS)

    def _lookup(self, key):
        try:
            result = self._make_result(get_lookup_json(self._url, key))
            failed = False
            reset_backoff()
        except urllib.error.HTTPError as exc:
            # Too many requests: all lookups stop for a while (see start_backoff), and this
            # one is tried again after that. Any other error is reported as below.
            if exc.code == 429:
                start_backoff(exc.headers.get("Retry-After"))
            else:
                print(f"Lookup of {key} failed: {error_text(exc)}", flush=True)
            result = None
            failed = True
        except OSError as exc:
            # Service slow or unreachable (a timeout, say): that happens now and then, so say so
            # in one line, and try again soon.
            print(f"Lookup of {key} failed: {error_text(exc)}", flush=True)
            result = None
            failed = True
        except Exception as exc:
            # Bad JSON or the like: nothing for now, and try again later.
            report_failure(f"Lookup of {key}", exc)
            result = None
            failed = False

        if result is not None:
            expiry = FOUND_EXPIRY_SECS
        elif failed:
            expiry = RETRY_EXPIRY_SECS
        else:
            expiry = MISSING_EXPIRY_SECS

        # Stored in a tuple so that "looked up, nothing found" (None) can be
        # told from "never looked up" (no entry at all)
        self._cache.add(key, (result,), expiry)

        with self._lock:
            self._pending.discard(key)

    def get(self, key):
        """Return the result for key (never changed after this, so treat it as
        read-only), or None if there isn't one yet. If it hasn't been looked up,
        that happens in the background, so ask again later."""
        item = self._cache.get(key)

        if item is None:
            with self._lock:
                if key in self._pending:
                    return None
                self._pending.add(key)

            self._queue.put(key)
            return None

        return item[0]