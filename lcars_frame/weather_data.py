"""
weather_data.py

Holds a copy of the weather data under common names that don't depend on the
weather provider. The code that fetches the data (currently Open-Meteo, in
lcars_weather.py) translates the provider's names and units into the ones
below. Change providers by writing a new translation; nothing that reads a
WeatherData needs to change.

Three classes describe one set of values each:

    CurrentWeather   the current observations
    HourlyWeather    one hour of the hourly forecast
    DailyWeather     one day of the daily forecast

Every value is a property with a getter and a setter. They all start as None,
meaning "the provider didn't supply it", and are filled in with the setters.
Nothing is checked.

Each class also has a read-only weather_description, the text for its
weather_code (e.g. 63 -> "RAIN"), or "Unknown" if the code is None.

CurrentWeather's wind_direction is set in degrees but read back as a
(degrees, compass point) tuple, e.g. (225, "SW").

CurrentWeather also has a read-only wind_beaufort, a (force, description)
tuple for its wind_speed, e.g. (5, "Fresh breeze"), or (None, "Unknown") if
there is no wind speed.

WeatherData holds one CurrentWeather plus lists of HourlyWeather and
DailyWeather:

    data = WeatherData()
    data.load(current, hourly, daily, last_success)

    data.current.temperature            # CurrentWeather
    data.hourly[3].precipitation        # list of HourlyWeather
    data.daily[0].temperature_max       # list of DailyWeather
    data.last_success                   # Unix timestamp (float), or None

    hour = HourlyWeather()
    hour.time = 1760552400
    hour.temperature = 11.2

UNITS (every provider's values are converted to these)
    time, sunrise, sunset     Unix timestamp, seconds, UTC
    temperature               degrees C
    humidity, cloud_cover,
    precipitation_probability percent, 0-100
    wind_speed, wind_gust     knots
    wind_direction            degrees, 0-360
    precipitation             mm (current: the current hour; hourly: the hour
                              ENDING at that time; daily: the day total)
    pressure                  hPa (mbar)
    visibility                metres
    uv_index                  UV index
    daylight_duration,
    sunshine_duration         seconds
    moon_phase                0 to 1 (0 = new, 0.5 = full)
    weather_code              WMO weather interpretation code

The data is deep-copied on the way into WeatherData (by load() and by the
setters), so later changes to the objects that were passed in don't alter this
one. The getters return the stored objects themselves (not further copies), so
treat what they return as read-only.
"""

import bisect
import copy


# WMO weather interpretation codes, the common weather_code format.
WMO_WEATHER_CODES = {
    0: "CLEAR", 1: "MOSTLY CLEAR", 2: "PARTLY CLOUDY", 3: "OVERCAST",
    45: "FOG", 48: "RIME FOG",
    51: "LIGHT DRIZZLE", 53: "DRIZZLE", 55: "DENSE DRIZZLE",
    56: "FREEZING DRIZZLE", 57: "FREEZING DRIZZLE",
    61: "LIGHT RAIN", 63: "RAIN", 65: "HEAVY RAIN",
    66: "FREEZING RAIN", 67: "FREEZING RAIN",
    71: "LIGHT SNOW", 73: "SNOW", 75: "HEAVY SNOW", 77: "SNOW GRAINS",
    80: "RAIN SHOWERS", 81: "RAIN SHOWERS", 82: "HEAVY SHOWERS",
    85: "SNOW SHOWERS", 86: "SNOW SHOWERS",
    95: "THUNDERSTORM", 96: "THUNDERSTORM", 99: "SEVERE STORM",
}


# Return a human-readable description for a WMO weather code.
def decode_weather_code(code):
    if code is None:
        return "Unknown"
    try:
        return WMO_WEATHER_CODES.get(int(code), f"Unknown code {code}")
    except (TypeError, ValueError):
        return f"Unknown code {code}"


# Lowest whole-knot speed for Beaufort forces 1 to 12 (force 0 is below 1 kt)
BEAUFORT_KNOTS = (1, 4, 7, 11, 17, 22, 28, 34, 41, 48, 56, 64)

BEAUFORT_NAMES = (
    "Calm", "Light air", "Light breeze", "Gentle breeze", "Moderate breeze",
    "Fresh breeze", "Strong breeze", "Near gale", "Gale", "Severe gale",
    "Storm", "Violent storm", "Hurricane force",
)


# Convert a wind speed in knots to (force, description),
# e.g. 18.2 -> (5, 'Fresh breeze'). Returns (None, 'Unknown') if missing.
def knots_to_beaufort(knots):
    if knots is None:
        return None, "Unknown"
    force = bisect.bisect_right(BEAUFORT_KNOTS, round(float(knots)))
    return force, BEAUFORT_NAMES[force]


COMPASS_POINTS = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")


# Convert a wind direction in degrees to a compass point, e.g. 225 -> 'SW'.
# Returns '' (blank) if missing or not a number.
def degrees_to_compass(degrees):
    if degrees is None:
        return ""
    try:
        index = round(float(degrees) / 45) % 8
    except (TypeError, ValueError):
        return ""
    return COMPASS_POINTS[index]


# The current observations.
class CurrentWeather:

    def __init__(self):
        self._time = None
        self._temperature = None
        self._apparent_temperature = None
        self._humidity = None
        self._wind_speed = None
        self._wind_direction = None
        self._wind_gust = None
        self._precipitation = None
        self._weather_code = None
        self._cloud_cover = None
        self._pressure = None
        self._precipitation_probability = None
        self._visibility = None


    # Unix timestamp of the observation
    @property
    def time(self):
        return self._time

    @time.setter
    def time(self, value):
        self._time = value


    # degrees C
    @property
    def temperature(self):
        return self._temperature

    @temperature.setter
    def temperature(self, value):
        self._temperature = value


    # degrees C
    @property
    def apparent_temperature(self):
        return self._apparent_temperature

    @apparent_temperature.setter
    def apparent_temperature(self, value):
        self._apparent_temperature = value


    # percent
    @property
    def humidity(self):
        return self._humidity

    @humidity.setter
    def humidity(self, value):
        self._humidity = value


    # knots
    @property
    def wind_speed(self):
        return self._wind_speed

    @wind_speed.setter
    def wind_speed(self, value):
        self._wind_speed = value


    # Beaufort (force, description) for wind_speed, e.g. (5, "Fresh breeze"),
    # or (None, "Unknown") if there is no wind speed. Read-only.
    @property
    def wind_beaufort(self):
        return knots_to_beaufort(self._wind_speed)


    # (degrees, compass point), e.g. (225, "SW"), or (None, "") if there is no
    # wind direction. The setter takes just the degrees (0-360).
    @property
    def wind_direction(self):
        return self._wind_direction, degrees_to_compass(self._wind_direction)

    @wind_direction.setter
    def wind_direction(self, value):
        self._wind_direction = value


    # knots
    @property
    def wind_gust(self):
        return self._wind_gust

    @wind_gust.setter
    def wind_gust(self, value):
        self._wind_gust = value


    # mm in the current hour
    @property
    def precipitation(self):
        return self._precipitation

    @precipitation.setter
    def precipitation(self, value):
        self._precipitation = value


    # WMO weather code
    @property
    def weather_code(self):
        return self._weather_code

    @weather_code.setter
    def weather_code(self, value):
        self._weather_code = value


    # Text for weather_code, e.g. "LIGHT RAIN". Read-only.
    @property
    def weather_description(self):
        return decode_weather_code(self._weather_code)


    # percent
    @property
    def cloud_cover(self):
        return self._cloud_cover

    @cloud_cover.setter
    def cloud_cover(self, value):
        self._cloud_cover = value


    # hPa
    @property
    def pressure(self):
        return self._pressure

    @pressure.setter
    def pressure(self, value):
        self._pressure = value


    # percent
    @property
    def precipitation_probability(self):
        return self._precipitation_probability

    @precipitation_probability.setter
    def precipitation_probability(self, value):
        self._precipitation_probability = value


    # metres
    @property
    def visibility(self):
        return self._visibility

    @visibility.setter
    def visibility(self, value):
        self._visibility = value



# One hour of the hourly forecast.
class HourlyWeather:

    def __init__(self):
        self._time = None
        self._temperature = None
        self._precipitation = None
        self._weather_code = None
        self._pressure = None


    # Unix timestamp of the hour
    @property
    def time(self):
        return self._time

    @time.setter
    def time(self, value):
        self._time = value


    # degrees C
    @property
    def temperature(self):
        return self._temperature

    @temperature.setter
    def temperature(self, value):
        self._temperature = value


    # mm
    @property
    def precipitation(self):
        return self._precipitation

    @precipitation.setter
    def precipitation(self, value):
        self._precipitation = value


    # WMO weather code
    @property
    def weather_code(self):
        return self._weather_code

    @weather_code.setter
    def weather_code(self, value):
        self._weather_code = value


    # Text for weather_code, e.g. "LIGHT RAIN". Read-only.
    @property
    def weather_description(self):
        return decode_weather_code(self._weather_code)


    # hPa
    @property
    def pressure(self):
        return self._pressure

    @pressure.setter
    def pressure(self, value):
        self._pressure = value



# One day of the daily forecast.
class DailyWeather:

    def __init__(self):
        self._time = None
        self._weather_code = None
        self._temperature_max = None
        self._temperature_min = None
        self._uv_index = None
        self._sunrise = None
        self._sunset = None
        self._daylight_duration = None
        self._sunshine_duration = None
        self._moon_phase = None
        self._precipitation = None
        self._precipitation_probability = None


    # Unix timestamp of the start of the day
    @property
    def time(self):
        return self._time

    @time.setter
    def time(self, value):
        self._time = value


    # WMO weather code
    @property
    def weather_code(self):
        return self._weather_code

    @weather_code.setter
    def weather_code(self, value):
        self._weather_code = value


    # Text for weather_code, e.g. "LIGHT RAIN". Read-only.
    @property
    def weather_description(self):
        return decode_weather_code(self._weather_code)


    # degrees C
    @property
    def temperature_max(self):
        return self._temperature_max

    @temperature_max.setter
    def temperature_max(self, value):
        self._temperature_max = value


    # degrees C
    @property
    def temperature_min(self):
        return self._temperature_min

    @temperature_min.setter
    def temperature_min(self, value):
        self._temperature_min = value


    # UV index (the day's maximum)
    @property
    def uv_index(self):
        return self._uv_index

    @uv_index.setter
    def uv_index(self, value):
        self._uv_index = value


    # Unix timestamp
    @property
    def sunrise(self):
        return self._sunrise

    @sunrise.setter
    def sunrise(self, value):
        self._sunrise = value


    # Unix timestamp
    @property
    def sunset(self):
        return self._sunset

    @sunset.setter
    def sunset(self, value):
        self._sunset = value


    # seconds
    @property
    def daylight_duration(self):
        return self._daylight_duration

    @daylight_duration.setter
    def daylight_duration(self, value):
        self._daylight_duration = value


    # seconds
    @property
    def sunshine_duration(self):
        return self._sunshine_duration

    @sunshine_duration.setter
    def sunshine_duration(self, value):
        self._sunshine_duration = value


    # 0 to 1 (0 = new, 0.5 = full)
    @property
    def moon_phase(self):
        return self._moon_phase

    @moon_phase.setter
    def moon_phase(self, value):
        self._moon_phase = value


    # mm, day total
    @property
    def precipitation(self):
        return self._precipitation

    @precipitation.setter
    def precipitation(self, value):
        self._precipitation = value


    # percent (the day's maximum)
    @property
    def precipitation_probability(self):
        return self._precipitation_probability

    @precipitation_probability.setter
    def precipitation_probability(self, value):
        self._precipitation_probability = value



class WeatherData:

    def __init__(self):
        self._current = CurrentWeather()
        self._hourly = []
        self._daily = []
        self._last_success = None


    # Replace everything in one go with a copy of the new data.
    # A missing (None) current becomes an empty CurrentWeather, and a missing
    # hourly or daily becomes an empty list.
    def load(self, current, hourly, daily, last_success):
        self.current = current
        self.hourly = hourly
        self.daily = daily
        self.last_success = last_success


    # The current observations, as a CurrentWeather.
    @property
    def current(self):
        return self._current

    @current.setter
    def current(self, value):
        assert value is None or isinstance(value, CurrentWeather), "CurrentWeather or None expected"
        self._current = copy.deepcopy(value) if value else CurrentWeather()


    # The hourly forecast, as a list of HourlyWeather.
    @property
    def hourly(self):
        return self._hourly

    @hourly.setter
    def hourly(self, value):
        items = list(value) if value else []
        assert all(isinstance(item, HourlyWeather) for item in items), "list of HourlyWeather expected"
        self._hourly = copy.deepcopy(items)


    # The daily forecast, as a list of DailyWeather.
    @property
    def daily(self):
        return self._daily

    @daily.setter
    def daily(self, value):
        items = list(value) if value else []
        assert all(isinstance(item, DailyWeather) for item in items), "list of DailyWeather expected"
        self._daily = copy.deepcopy(items)


    # Unix timestamp (float) of the last successful fetch, or None if there
    # has never been one.
    @property
    def last_success(self):
        return self._last_success

    @last_success.setter
    def last_success(self, value):
        self._last_success = value
        
        