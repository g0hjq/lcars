# LCARS display

A Star Trek LCARS-style display for a Raspberry Pi 5, written in Python with pygame. It
shows one screen at a time:

- **LCARS**: clock, weather, calendar and an aircraft radar (`lcars_frame/`)
- **DeviantArt frame**: a picture frame that downloads new pictures every day (`deviantart_frame/`)
- **Biomonitor**: sickbay biomonitor dials (`biomonitor_frame/`)

## Buttons and keys

Three push buttons on the GPIO pins (see `gpio_buttons.py`), or the keyboard:

| Button | Key | Does |
| --- | --- | --- |
| PREVIOUS (GPIO22) | Left arrow | previous screen |
| NEXT (GPIO17) | Right arrow | next screen |
| OK (GPIO27), brief press | Enter / space | DeviantArt frame: next picture |
| OK, held 2 seconds | Delete | DeviantArt frame: delete the picture shown |
| | Esc / Q | quit |

## Running it

```
./enable_service.sh     # start it now, and at every boot (the lcars systemd service)
./disable_service.sh    # stop it, and don't start it at boot
```

To see its messages: `journalctl -u lcars -f`. To run it by hand instead, run
`./disable_service.sh`, then `SDL_VIDEODRIVER=kmsdrm python3 lcars.py`.

## Your own settings

Copy `my_settings_example.py` to `my_settings.py` and put in where you are (for the
weather and the aircraft radar) and the address of your ADS-B receiver.

## Files not in the repository

These hold keys or logins, or are made as it runs, so they are left out (see `.gitignore`):

- `my_settings.py`: your location and receiver address
- `deviantart_frame/deviantart_key.txt`: your DeviantArt API client_id and client_secret
- `lcars_frame/credentials.json` and `lcars_frame/token.json`: the Google Calendar login
- `deviantart_frame/deviantart_choices.txt`: what the DeviantArt frame shows (made if it isn't there)
- `deviantart_frame/pictures/`: the downloaded pictures
