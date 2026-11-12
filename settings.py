# settings.py
#
# Your own settings from my_settings.py, or, if that hasn't been made yet, the made-up
# ones in my_settings_example.py. Use these with: from settings import HOME_LAT

try:
    from my_settings import *               # noqa: F401,F403
except ImportError:
    print("No my_settings.py, so using the made-up settings in my_settings_example.py")
    from my_settings_example import *       # noqa: F401,F403
