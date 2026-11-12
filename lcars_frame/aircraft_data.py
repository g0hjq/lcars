"""
aircraft_data.py

Holds a copy of the aircraft seen by your ADS-B receiver, under common names
that don't depend on the receiver software. The code that fetches them
(currently dump1090, in aircraft.py) translates its names and formats into the
ones below. Nothing that reads an AircraftData needs to know where it came from.

Four classes:

    Aircraft        one aircraft
    AircraftData    a list of Aircraft plus the time of the last fetch
    Route           an airline's flight: where it is going from and to
    AircraftType    what kind of aircraft it is
    (the last two are looked up separately, see lookups.py)

Every value of an Aircraft is a property with a getter and a setter. They all
start as None, meaning "the receiver didn't supply it", and are filled in with
the setters. Nothing is checked.

    data = AircraftData()
    data.load(aircraft)                 # also sets last_success to the time now

    data.aircraft[0].callsign           # list of Aircraft, nearest first
    data.last_success                   # Unix timestamp (float), or None

    plane = Aircraft()
    plane.callsign = "BAW123"
    plane.altitude_ft = 12000

UNITS (every receiver's values are converted to these)
    icao                text, the aircraft's 6-digit hex address, e.g. '4CA7B1'
    callsign            text, e.g. 'BAW123'
    altitude_ft         feet, barometric (0 if on the ground)
    on_ground           True or False
    speed_kt            knots, ground speed
    track_deg           degrees true, the direction it is heading (0 = north)
    vertical_rate_fpm   feet per minute (negative = descending)
    latitude            degrees
    longitude           degrees
    distance_nm         nautical miles from your receiver
    bearing_deg         degrees true, the direction from your receiver to it
    squawk              text, the 4-digit transponder code, e.g. '7000'
    category            text, the emitter category the aircraft transmits, e.g. 'A3' (large)
    military            True if it looks like a military aircraft (see looks_military)
    service             what emergency service it looks like it belongs to, e.g. 'POLICE' (see
                        service_for_callsign), otherwise None
    trail               where it has been: a tuple of (bearing_deg, distance_nm) pairs
                        from your receiver, oldest first, not including where it is now

The data is deep-copied on the way into AircraftData (by load() and by the
setters), so later changes to the objects that were passed in don't alter this
one. The getters return the stored objects themselves (not further copies), so
treat what they return as read-only.
"""

import copy
import time


# Transponder codes that mean an emergency, and what each means
EMERGENCY_SQUAWKS = {
    "7500": "HIJACK",
    "7600": "RADIO FAILURE",
    "7700": "EMERGENCY",
}

# The kinds of aircraft that an emitter category stands for (see Aircraft.kind): A1 to A7
# are the aeroplanes and helicopter classes that every transponder can give; the rest of
# the categories (gliders, balloons, drones, vehicles...) are left as None.
CATEGORY_KINDS = {
    "A1": "LIGHT",          # up to 15,500 lb
    "A2": "SMALL",         # up to 75,000 lb
    "A3": "LARGE",         # up to 300,000 lb, e.g. an A320 or 737
    "A4": "LARGE",         # high vortex, e.g. the 757
    "A5": "HEAVY",         # over 300,000 lb, e.g. a 747 or A330
    "A6": "FAST",          # high performance (over 5 g and 400 kt), e.g. a fighter
    "A7": "HELICOPTER",
}

# Blocks of the six-digit hex addresses that belong to military aircraft, as (first, last).
# These are the published national allocations, from memory, so they are not complete:
# add more as you find them.
MILITARY_ICAO_RANGES = (
    (0xADF7C8, 0xAFFFFF),       # United States
    (0x43C000, 0x43CFFF),       # United Kingdom
    (0x3A8000, 0x3AFFFF),       # France
    (0x3EA000, 0x3EBFFF),       # Germany
    (0x3F4000, 0x3FBFFF),       # Germany
    (0x33FF00, 0x33FFFF),       # Italy
    (0x480000, 0x480FFF),       # Netherlands
    (0x44F000, 0x44FFFF),       # Belgium
    (0xC0CDF9, 0xC3FFFF),       # Canada
)

# The starts of callsigns that military flights use, e.g. RRR7123 (Royal Air Force) or
# RCH123 (the US Air Force's transports). A callsign counts when one of these is followed
# by a digit, so that a civil airline's flight that happens to start with the same letters
# isn't taken for one.
MILITARY_CALLSIGN_PREFIXES = (
    "RRR", "RFR", "RAF", "ASCOT", "NATO", "RCH", "CNV", "NAVY", "PAT", "SAM",
    "GAF", "FAF", "BAF", "NAF", "IAM", "CFC",
)


# The starts of callsigns that the emergency services' flights use, and what each stands for, e.g.
# POLICE71 (a police helicopter) or RESCUE199 (a coastguard helicopter). As for the military ones, a
# callsign counts when the start is followed by a digit. These are from memory, so they are not
# complete: add more as you find them.
EMERGENCY_SERVICE_CALLSIGNS = {
    "POLICE": "POLICE",
    "NPAS": "POLICE",
    "UKP": "POLICE",            # National Police Air Service helicopters, e.g. UKP151 (G-POLC)
    "RESCUE": "RESCUE",
    "COASTGUARD": "COASTGUARD",
    "AMBULANCE": "AMBULANCE",
    "HELIMED": "AIR AMBULANCE",
    "HELMED": "AIR AMBULANCE",  # e.g. HELMED7
    "AIRMED": "AIR AMBULANCE",
    "MEDEVAC": "MEDICAL",
    "MEDIC": "MEDICAL",
    "LIFEGUARD": "MEDICAL",
}


# True if the hex address is in one of the military blocks
def icao_is_military(icao):
    try:
        address = int(icao, 16)
    except (TypeError, ValueError):
        return False

    return any(first <= address <= last for first, last in MILITARY_ICAO_RANGES)


# True if the callsign starts like a military one: see MILITARY_CALLSIGN_PREFIXES
def callsign_is_military(callsign):
    if not callsign:
        return False

    for prefix in MILITARY_CALLSIGN_PREFIXES:
        if callsign.startswith(prefix) and callsign[len(prefix):len(prefix) + 1].isdigit():
            return True

    return False


# What emergency service the callsign says it belongs to ('POLICE', 'RESCUE'...), or None if it
# doesn't start like one of theirs: see EMERGENCY_SERVICE_CALLSIGNS
def service_for_callsign(callsign):
    if not callsign:
        return None

    for prefix, service in EMERGENCY_SERVICE_CALLSIGNS.items():
        if callsign.startswith(prefix) and callsign[len(prefix):len(prefix) + 1].isdigit():
            return service

    return None


# True if the aircraft looks military, from its hex address or its callsign. It is a
# good guess and not a certainty: a block can hold civil aircraft, and a military
# flight can use an ordinary callsign.
def looks_military(icao, callsign):
    return icao_is_military(icao) or callsign_is_military(callsign)


# One aircraft.
class Aircraft:

    def __init__(self):
        self._icao = None
        self._callsign = None
        self._altitude_ft = None
        self._on_ground = None
        self._speed_kt = None
        self._track_deg = None
        self._vertical_rate_fpm = None
        self._latitude = None
        self._longitude = None
        self._distance_nm = None
        self._bearing_deg = None
        self._squawk = None
        self._category = None
        self._military = None
        self._service = None
        self._trail = ()


    # The aircraft's hex address
    @property
    def icao(self):
        return self._icao

    @icao.setter
    def icao(self, value):
        self._icao = value


    # The flight number / registration it is transmitting
    @property
    def callsign(self):
        return self._callsign

    @callsign.setter
    def callsign(self, value):
        self._callsign = value


    # Barometric altitude, in feet
    @property
    def altitude_ft(self):
        return self._altitude_ft

    @altitude_ft.setter
    def altitude_ft(self, value):
        self._altitude_ft = value


    # True if it is on the ground
    @property
    def on_ground(self):
        return self._on_ground

    @on_ground.setter
    def on_ground(self, value):
        self._on_ground = value


    # Ground speed, in knots
    @property
    def speed_kt(self):
        return self._speed_kt

    @speed_kt.setter
    def speed_kt(self, value):
        self._speed_kt = value


    # The direction it is heading, in degrees true
    @property
    def track_deg(self):
        return self._track_deg

    @track_deg.setter
    def track_deg(self, value):
        self._track_deg = value


    # Climb (positive) or descent (negative), in feet per minute
    @property
    def vertical_rate_fpm(self):
        return self._vertical_rate_fpm

    @vertical_rate_fpm.setter
    def vertical_rate_fpm(self, value):
        self._vertical_rate_fpm = value


    # Latitude, in degrees
    @property
    def latitude(self):
        return self._latitude

    @latitude.setter
    def latitude(self, value):
        self._latitude = value


    # Longitude, in degrees
    @property
    def longitude(self):
        return self._longitude

    @longitude.setter
    def longitude(self, value):
        self._longitude = value


    # Distance from your receiver, in nautical miles
    @property
    def distance_nm(self):
        return self._distance_nm

    @distance_nm.setter
    def distance_nm(self, value):
        self._distance_nm = value


    # The direction from your receiver to the aircraft, in degrees true
    @property
    def bearing_deg(self):
        return self._bearing_deg

    @bearing_deg.setter
    def bearing_deg(self, value):
        self._bearing_deg = value


    # The 4-digit transponder code
    @property
    def squawk(self):
        return self._squawk

    @squawk.setter
    def squawk(self, value):
        self._squawk = value


    # The emitter category it transmits, like 'A3'
    @property
    def category(self):
        return self._category

    @category.setter
    def category(self, value):
        self._category = value


    # True if it looks like a military aircraft
    @property
    def military(self):
        return self._military

    @military.setter
    def military(self, value):
        self._military = value


    # The emergency service it looks like it belongs to ('POLICE'...), otherwise None
    @property
    def service(self):
        return self._service

    @service.setter
    def service(self, value):
        self._service = value


    # What the squawk means if it is an emergency code ('EMERGENCY', 'RADIO FAILURE' or
    # 'HIJACK'), otherwise None
    @property
    def emergency(self):
        return EMERGENCY_SQUAWKS.get(self._squawk)


    # The kind of aircraft its category says: 'LIGHT', 'SMALL', 'LARGE', 'HEAVY', 'FAST' (high
    # performance) or 'HELICOPTER', or None if it doesn't say or isn't one of those
    @property
    def kind(self):
        return CATEGORY_KINDS.get(self._category)


    # Where it has been, as (bearing, distance) pairs from your receiver, oldest first
    @property
    def trail(self):
        return self._trail

    @trail.setter
    def trail(self, value):
        self._trail = value



# An airline's flight: who flies it and where it is going from and to. Anything that
# isn't known is None. The airports are given as a code ('MAN') and as the name of the
# place they serve ('Manchester').
class Route:

    def __init__(self):
        self._airline = None
        self._origin = None
        self._origin_name = None
        self._destination = None
        self._destination_name = None


    # The airline, e.g. 'Ryanair'
    @property
    def airline(self):
        return self._airline

    @airline.setter
    def airline(self, value):
        self._airline = value


    # The airport it took off from, as a code like 'PRG'
    @property
    def origin(self):
        return self._origin

    @origin.setter
    def origin(self, value):
        self._origin = value


    # ...and the name of the place, like 'Prague'
    @property
    def origin_name(self):
        return self._origin_name

    @origin_name.setter
    def origin_name(self, value):
        self._origin_name = value


    # The airport it is going to, as a code like 'MAN'
    @property
    def destination(self):
        return self._destination

    @destination.setter
    def destination(self, value):
        self._destination = value


    # ...and the name of the place, like 'Manchester'
    @property
    def destination_name(self):
        return self._destination_name

    @destination_name.setter
    def destination_name(self, value):
        self._destination_name = value



# What kind of aircraft it is. Anything that isn't known is None.
class AircraftType:

    def __init__(self):
        self._manufacturer = None
        self._model = None
        self._registration = None


    # The maker, e.g. 'Boeing'
    @property
    def manufacturer(self):
        return self._manufacturer

    @manufacturer.setter
    def manufacturer(self, value):
        self._manufacturer = value


    # The model, e.g. '737-8AS'
    @property
    def model(self):
        return self._model

    @model.setter
    def model(self, value):
        self._model = value


    # The registration painted on the tail, e.g. 'EI-DLH'
    @property
    def registration(self):
        return self._registration

    @registration.setter
    def registration(self, value):
        self._registration = value



class AircraftData:

    def __init__(self):
        self._aircraft = []
        self._last_success = None


    # Replace the aircraft with a copy of the new ones, and set last_success to
    # the current time. A missing (None) list becomes an empty list.
    def load(self, aircraft):
        self.aircraft = aircraft
        self.last_success = time.time()


    # The aircraft, nearest first, as a list of Aircraft.
    @property
    def aircraft(self):
        return self._aircraft

    @aircraft.setter
    def aircraft(self, value):
        items = list(value) if value else []
        assert all(isinstance(item, Aircraft) for item in items), "list of Aircraft expected"
        self._aircraft = copy.deepcopy(items)


    # Unix timestamp (float) of the last load(), i.e. the last successful
    # fetch, or None if there has never been one.
    @property
    def last_success(self):
        return self._last_success

    @last_success.setter
    def last_success(self, value):
        self._last_success = value
        