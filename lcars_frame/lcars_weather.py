"""
Background Open-Meteo weather fetcher.

Runs in a daemon thread, refreshing a module-level WeatherData (see
weather_data.py) every 30 minutes. This is the only place that knows about
Open-Meteo's field names and units: they are translated into the
provider-independent classes here, so changing weather provider only means
changing this file.
Uses only the Python standard library.
"""


import json
import os
import threading
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from .weather_data import CurrentWeather, HourlyWeather, DailyWeather, WeatherData


# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

from settings import WEATHER_LAT as LATITUDE, WEATHER_LON as LONGITUDE   # from my_settings.py

# Its settings are in settings.py (next to lcars.py)
from settings import (
    WEATHER_FORECAST_DAYS as FORECAST_DAYS,
    WEATHER_UPDATE_INTERVAL as UPDATE_INTERVAL,
    WEATHER_RETRY_INTERVAL as RETRY_INTERVAL,
    WEATHER_REQUEST_TIMEOUT as REQUEST_TIMEOUT,
    WEATHER_DEBUG as DEBUG,
)


# The Open-Meteo variables to ask for. Open-Meteo's units already match the
# ones weather_data.py uses: the request asks for knots and Unix times, and it
# reports degrees C, hPa, mm, metres and seconds.
CURRENT_VARIABLES = [
    "temperature_2m",
    "relative_humidity_2m",
    "apparent_temperature",
    "wind_speed_10m",
    "wind_direction_10m",
    "wind_gusts_10m",
    "precipitation",
    "weather_code",
    "cloud_cover",
    "surface_pressure",
    "precipitation_probability",
    "visibility"
]


HOURLY_VARIABLES = [
    "temperature_2m",
    "precipitation",
    "weather_code",
    "surface_pressure",
]


DAILY_VARIABLES = [
    "weather_code",
    "temperature_2m_max",
    "temperature_2m_min",
    "uv_index_max",
    "sunrise",
    "sunset",
    "daylight_duration",
    "sunshine_duration",
    "moon_phase",
    "precipitation_sum",
    "precipitation_probability_max"
]


# --------------------------------------------------------------------------
# Global state
#
# The weather code descriptions and the Beaufort scale live in weather_data.py,
# as the weather_description and wind_beaufort properties.
# --------------------------------------------------------------------------

_lock = threading.Lock()
_thread = None

_weather = WeatherData()    # the latest good data; replaced, never changed

_status = {
    "last_attempt": None,   # Unix timestamp (float) of last fetch attempt
    "last_error": None,     # str, or None if the last attempt succeeded
    "update_count": 0,      # incremented on every successful update
}


def get_weather():
    """Return the latest WeatherData. It is never changed after this (the next
    update makes a new one), so treat it as read-only."""
    with _lock:
        return _weather


def get_status():
    """Return a thread-safe copy of the fetch status (last_attempt, last_error, update_count)."""
    with _lock:
        return dict(_status)


def get_update_count():
    """
    Number of successful updates so far. Cheap enough to poll every frame:
    when it changes, new data is available from get_weather().
    """
    with _lock:
        return _status["update_count"]


# --------------------------------------------------------------------------
# Fetching
# --------------------------------------------------------------------------

class WeatherError(Exception):
    """Raised for any failure fetching or parsing weather data."""


def error_location(exc):
    """
    Return where an exception was raised, e.g.
    "lcars_weather.py line 209 in fetch_weather_data(): <source line>".
    Uses the innermost frame of the traceback, i.e. the line that failed.
    """
    frames = traceback.extract_tb(exc.__traceback__)
    if not frames:
        return "unknown location"

    frame = frames[-1]
    location = f"{os.path.basename(frame.filename)} line {frame.lineno} in {frame.name}()"
    if frame.line:
        location += f": {frame.line.strip()}"
    return location


# --------------------------------------------------------------------------
# Translating Open-Meteo's data into the weather_data classes
# --------------------------------------------------------------------------

# Value at position `index` of a list in an Open-Meteo block,
# or None if the key is missing or the list is too short.
def value_at(block, key, index):
    values = block.get(key) or []
    if 0 <= index < len(values):
        return values[index]
    return None


# The Open-Meteo "current" block as a CurrentWeather.
def build_current(block):
    current = CurrentWeather()
    current.time = block.get("time")
    current.temperature = block.get("temperature_2m")
    current.apparent_temperature = block.get("apparent_temperature")
    current.humidity = block.get("relative_humidity_2m")
    current.wind_speed = block.get("wind_speed_10m")
    current.wind_direction = block.get("wind_direction_10m")
    current.wind_gust = block.get("wind_gusts_10m")
    current.precipitation = block.get("precipitation")
    current.weather_code = block.get("weather_code")
    current.cloud_cover = block.get("cloud_cover")
    current.pressure = block.get("surface_pressure")
    current.precipitation_probability = block.get("precipitation_probability")
    current.visibility = block.get("visibility")
    return current


# The Open-Meteo "hourly" block as a list of HourlyWeather, one per hour.
def build_hourly(block):
    hours = []

    for i in range(len(block.get("time") or [])):
        hour = HourlyWeather()
        hour.time = value_at(block, "time", i)
        hour.temperature = value_at(block, "temperature_2m", i)
        hour.precipitation = value_at(block, "precipitation", i)
        hour.weather_code = value_at(block, "weather_code", i)
        hour.pressure = value_at(block, "surface_pressure", i)
        hours.append(hour)

    return hours


# The Open-Meteo "daily" block as a list of DailyWeather, one per day.
def build_daily(block):
    days = []

    for i in range(len(block.get("time") or [])):
        day = DailyWeather()
        day.time = value_at(block, "time", i)
        day.weather_code = value_at(block, "weather_code", i)
        day.temperature_max = value_at(block, "temperature_2m_max", i)
        day.temperature_min = value_at(block, "temperature_2m_min", i)
        day.uv_index = value_at(block, "uv_index_max", i)
        day.sunrise = value_at(block, "sunrise", i)
        day.sunset = value_at(block, "sunset", i)
        day.daylight_duration = value_at(block, "daylight_duration", i)
        day.sunshine_duration = value_at(block, "sunshine_duration", i)
        day.moon_phase = value_at(block, "moon_phase", i)
        day.precipitation = value_at(block, "precipitation_sum", i)
        day.precipitation_probability = value_at(block, "precipitation_probability_max", i)
        days.append(day)

    return days


# Fetch from Open-Meteo.
# Returns (CurrentWeather, [HourlyWeather], [DailyWeather]).
def fetch_weather_data():
    params = {
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        "current": ",".join(CURRENT_VARIABLES),
        "hourly": ",".join(HOURLY_VARIABLES),
        "daily": ",".join(DAILY_VARIABLES),
        "timezone" : "Europe/London",
        "timeformat": "unixtime",
        "wind_speed_unit": "kn",
        "forecast_days" : FORECAST_DAYS
    }
    url = f"{OPEN_METEO_URL}?{urllib.parse.urlencode(params, safe=',')}"
    if DEBUG:
        print(f"Weather request: {url}")

    request = urllib.request.Request(url, headers={"User-Agent": "python-urllib-weather/1.0"})

    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            data = json.load(response)
    except urllib.error.HTTPError as exc:
        try:
            reason = json.load(exc).get("reason", exc.reason)
        except Exception:
            reason = exc.reason
        raise WeatherError(f"HTTP {exc.code}: {reason}") from None
    except urllib.error.URLError as exc:
        raise WeatherError(f"Network error: {exc.reason}") from None
    except TimeoutError:
        raise WeatherError(f"Request timed out after {REQUEST_TIMEOUT}s") from None
    except ValueError as exc:
        raise WeatherError(f"Invalid JSON: {exc}") from None
    except OSError as exc:
        raise WeatherError(f"Connection error: {exc}") from None

    if not isinstance(data, dict):
        raise WeatherError("Unexpected response format")
    if data.get("error"):
        raise WeatherError(f"API error: {data.get('reason', 'unknown')}")

    current_block = data.get("current")
    hourly_block = data.get("hourly")
    daily_block = data.get("daily")

    if not isinstance(current_block, dict) or "time" not in current_block:
        raise WeatherError("Response has no usable 'current' block")

    if not isinstance(hourly_block, dict) or "time" not in hourly_block:
        raise WeatherError("Response has no usable 'hourly' block")

    if not isinstance(daily_block, dict) or "time" not in daily_block:
        raise WeatherError("Response has no usable 'daily' block")

    return build_current(current_block), build_hourly(hourly_block), build_daily(daily_block)


def update_weather():
    """
    Fetch once and update the global data.
    Returns True on success, False on failure. Never raises.
    """
    global _weather
    ts = datetime.now(timezone.utc).timestamp()
    try:
        current, hourly, daily = fetch_weather_data()
    except WeatherError as exc:
        error = f"{exc} [{error_location(exc)}]"
    except Exception as exc:  # safety net: never let the thread die
        error = f"Unexpected error: {exc!r} [{error_location(exc)}]"
        print("Unexpected error updating weather")
        traceback.print_exc()   # full call chain, with every line number
    else:
        # A new WeatherData each time, which is never changed once it is
        # published, so readers can hold on to the one they were given.
        weather = WeatherData()
        weather.load(current, hourly, daily, ts)
        with _lock:
            _weather = weather
            _status["last_attempt"] = ts
            _status["last_error"] = None
            _status["update_count"] += 1
        if DEBUG:
            print(f"Weather updated: {current.weather_description}, "
                  f"{current.temperature}c")

        return True


    # Failure: keep the last good reading, just record the error.
    with _lock:
        _status["last_attempt"] = ts
        _status["last_error"] = error
        print(f"Weather update failed: {error}")

    return False


# --------------------------------------------------------------------------
# Background thread
# --------------------------------------------------------------------------

def _worker():
    print("Weather thread started")
    while True:
        ok = update_weather()
        time.sleep(UPDATE_INTERVAL if ok else RETRY_INTERVAL)


def start_weather_thread():
    """Start the background updater (safe to call more than once)."""
    global _thread
    if _thread is not None and _thread.is_alive():
        return _thread
    _thread = threading.Thread(target=_worker, name="weather-updater", daemon=True)
    _thread.start()
    return _thread
    
    