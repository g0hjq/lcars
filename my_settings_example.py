# my_settings_example.py
#
# Your own settings: where you are, and where your aircraft receiver is. Copy this file
# to my_settings.py and put your own in there. my_settings.py is left out of git (see
# .gitignore), so they stay private; until it is made, the made-up ones here are used.
#
# It is read after settings.py, so any setting from there can be put here too, to change it
# without changing settings.py.

# Where your aircraft receiver is, in degrees. The distance and bearing of each aircraft,
# and where the airport is drawn on the radar, are worked out from here.
HOME_LAT = 53.40
HOME_LON = -2.20

# Where the weather forecast is for, in degrees
WEATHER_LAT = 53.40
WEATHER_LON = -2.20

# The aircraft.json of your dump1090 (or similar) ADS-B receiver
AIRCRAFT_URL = "http://localhost/dump1090/data/aircraft.json"
