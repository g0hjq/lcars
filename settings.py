"""
settings.py

Every setting of the program, in one place, a section for each part of it:

    THE DISPLAY                                     SCREEN_...
    THE BUTTONS                                     BUTTONS_...
    FONTS                                           FONT_...
    LCARS SCREEN                                    LCARS_...
    LCARS SCREEN: SOUND                             LCARS_SOUND_...
    LCARS SCREEN: HOW ITS PARTS MOVE AND LOOK       SHAPES_...
    LCARS SCREEN: THE WEATHER FORECAST              WEATHER_...
    LCARS SCREEN: THE AIRCRAFT                      AIRCRAFT_...
    LCARS SCREEN: EACH AIRCRAFT'S ROUTE AND MODEL   LOOKUP_...
    LCARS SCREEN: THE CALENDAR                      CALENDAR_...
    DEPARTURES BOARD                                DEPARTURES_...
    DEVIANTART FRAME                                DEVIANTART_...
    DEVIANTART FRAME: DOWNLOADING THE PICTURES      DOWNLOAD_...
    BIOMONITOR                                      BIOMONITOR_...
    CLOCK SCREEN                                    CLOCK_...
    CLOCK: BRASS FACE                               BRASS_...
    CLOCK: RAILWAY FACE                             RAILWAY_...
    CLOCK: DECO FACE                                DECO_...
    CLOCK: NIXIE FACE                               NIXIE_...
    CLOCK: FLIP FACE                                FLIP_...
    AQUARIUM                                        AQUARIUM_...
    VIEWSCREEN                                      VIEWSCREEN_...
    YOUR OWN SETTINGS                               (from my_settings.py, at the end)

Each setting's name starts with its section's, so search for, say, "AQUARIUM_" to find
all of the aquarium's. Sizes and positions are in pixels on the 1920 x 1080 screen, times
in seconds, and colours are (red, green, blue), each 0 to 255, unless it says otherwise.
Change them here, and restart the program (sudo systemctl restart lcars).

Your own settings (where you are, and your aircraft receiver) are in my_settings.py, which
is kept out of git so that they stay private. It is read last, so anything set in it
replaces the setting here: put any of these you have changed there too, if you like, to
keep your changes apart from the program's.

In the program each file takes its own settings with "from settings import ...", under
shorter names (LCARS_RADAR_SIZE is RADAR_SIZE in lcars_screen.py).
"""


##==================================================================
## THE DISPLAY (screens.py, lcars.py)
#
# The size of the display, how often it is redrawn, and the volumes the SOUND button
# goes round.
##==================================================================

# --- from screens.py ------------------------------------------
# The size of the display, which every screen fills
SCREEN_WIDTH = 1920
SCREEN_HEIGHT = 1080

SCREEN_NOTICE_SECONDS = 2.5            # how long the volume is shown after it is changed

# The volumes the SOUND button goes round, and how loud each is: high is the loudness each
# screen sets for itself, and medium and low are 6 and 12 dB quieter
SCREEN_VOLUMES = [("OFF", 0.0), ("LOW", 0.25), ("MEDIUM", 0.5), ("HIGH", 1.0)]
SCREEN_VOLUME_ORDER = [1, 2, 3, 0]     # low, medium, high, off, and round again

# --- from lcars.py --------------------------------------------
SCREEN_FRAME_RATE = 30


##==================================================================
## THE BUTTONS (gpio_buttons.py)
#
# The GPIO pins (BCM numbers) the push buttons are wired to, and how they are read.
##==================================================================

BUTTONS_SOUND_PIN = 22                  # (it was the PREVIOUS button)
BUTTONS_NEXT_PIN = 17
BUTTONS_OK_PIN = 27
BUTTONS_HOLD_SECONDS = 2            # how long the OK or SOUND button must be held down
BUTTONS_BOUNCE_SECONDS = 0.10       # a press within this long of the last is taken as contact bounce


##==================================================================
## FONTS (fonts.py)
#
# The font the text is in (from the fonts folder), and its sizes.
##==================================================================

FONT_FILE = "Antonio-Regular.ttf"
FONT_FILE_BOLD = "Antonio-Bold.ttf"
FONT_FILE_SCALE = 0.85      # the sizes below suit Arial; Antonio's letters are taller, so it is drawn smaller

#FONT_NAME = "agency fb"
FONT_NAME = "arial"
FONT_SIZE_XS = 18
FONT_SIZE_SMALL = 22
FONT_SIZE_LIST = 25         # the list of aircraft beside the radar, which is read from further away
FONT_SIZE_MEDIUM = 26
FONT_SIZE_LARGE = 36
FONT_SIZE_XL = 80
FONT_SIZE_XXL = 160


##==================================================================
## LCARS SCREEN (lcars_frame/lcars_screen.py)
#
# Its layout, the weather graphs, the Captain's Log, the radar and the list of aircraft
# beside it, and the emergency popup. A colour or a text size in quotes is one of the LCARS
# palette's (Colours in lcars_frame/lcars_shapes.py), or one of fonts.TextSize.
##==================================================================

# --- Layout and colours --------------------------------------------

LCARS_BORDER = 10                       # the space round the edge of the screen
LCARS_HEADER_LEFT_END = 990             # a title's line runs on to here for the sections on the left
                                        # (and to the right edge, less LCARS_BORDER, on the right)
LCARS_RIGHT_AREA_X = 1020               # the right-hand side of the screen starts here
LCARS_LOG_CHRONO_GAP = 20               # space between the Captain's Log and the Chronometer
LCARS_DIMMED = 0.8                      # the second border and sidebar colours are the first ones this bright
LCARS_LIGHTER = 0.2                     # how far the border and sidebar colours are moved towards white (0 = as they are, 1 = white)

# The labels on the sidebar's blocks, from the top
LCARS_SIDEBAR_LABELS = ("LCARS-III", "NET", "COM", "GLP", "ENV",
                        "MAIN", "BYP", "NWC", "FEK", "SHF", "ARS")

LCARS_CPU_RATE = 30                     # how often to update the CPU and memory display, in seconds

# --- The weather ----------------------------------------------------

LCARS_FORECAST_COUNT = 12               # the forecast across the top: this many times...
LCARS_FORECAST_STEP_HOURS = 2           # ...this many hours apart
LCARS_ICON_SIZE_SMALL = 60              # the weather icons in that forecast...
LCARS_ICON_SIZE_LARGE = 200             # ...and the big one for the weather now
LCARS_GRAPH_DAYS = 3                    # the graphs show this many days of the forecast, starting with the first day of it (today)
LCARS_GRAPH_WIDTH = 250                 # width of each of the three weather graphs, in pixels
LCARS_GRAPH_GAP = 20                    # and the space between them
LCARS_WEATHER_STALE_SECONDS = 60 * 60   # weather older than this is flagged in red

# --- The Captain's Log (your calendar) ------------------------------

LCARS_CALENDAR_EVENT_COUNT = 5          # how many of your next events it shows
LCARS_CALENDAR_COLUMN_GAP = 20          # pixels between the Captain's Log date, time and event columns

# --- The radar ------------------------------------------------------

LCARS_RADAR_SIZE = 470                  # width and height of the radar, in pixels
LCARS_RADAR_RING_NM = 5                 # a ring on the radar every this many nautical miles
LCARS_RADAR_ICON_BIG = 20               # size of an aircraft's icon (pixels from centre to nose) at ground level...
LCARS_RADAR_ICON_SMALL = 5              # ...and at LCARS_RADAR_ALTITUDE_MAX_FT or higher
LCARS_RADAR_ALTITUDE_MAX_FT = 20000
LCARS_RADAR_PASSING_FT = 15000          # an aircraft above this is just passing over, so it is drawn smaller...
LCARS_RADAR_ICON_PASSING = 3            # ...at this size
LCARS_RADAR_VERTICAL_FPM = 300          # it counts as climbing or descending at this many feet per minute or more
LCARS_RADAR_PROJECT_SECONDS = 10        # an aircraft is moved on from where it was last reported for at most this long

# An aircraft that is level is drawn in the sidebar colour. One that is climbing is drawn in whichever
# of these is furthest from that colour, and one that is descending likewise, so they can't be mistaken for it.
LCARS_RADAR_CLIMB_COLOURS = ("ICE_BLUE", "BLUE", "LILAC")
LCARS_RADAR_DESCEND_COLOURS = ("ORANGE", "SALMON", "RED")

# --- The airport on the radar (routes are only shown for flights to or from LOOKUP_HOME_AIRPORT)

LCARS_AIRPORT_NAME = "MAN"              # the airport marked on the radar (Manchester Airport)
LCARS_AIRPORT_LAT = 53.3538
LCARS_AIRPORT_LON = -2.2750

# Manchester's two runways, drawn to scale: (latitude, longitude) of each end, in
# degrees (the published threshold positions, from skyvector.com/airport/EGCC)
LCARS_AIRPORT_RUNWAYS = (
    ((53.33200, -2.31067), (53.34817, -2.27717)),      # 05R / 23L
    ((53.34750, -2.28783), (53.36133, -2.25933)),      # 05L / 23R
)

# --- The list of aircraft beside the radar --------------------------

LCARS_CONTACT_COUNT = 6                 # how many aircraft are listed (the lowest ones: see listOrder)
LCARS_LIST_NM_PER_1000_FT = 1.0         # in the order of the list, each 1000 feet of height counts as this many nautical miles away
LCARS_CONTACT_TEXT_SIZE = "LIST"        # the text size of that list (FONT_SIZE_LIST)
LCARS_CONTACT_COLUMN_GAP = 20           # pixels added to each column of that list, on top of its widest text
LCARS_CONTACT_LINE_1_GAP = 18           # ...but the columns of the first line after the number have less, to leave room for the model
LCARS_CONTACT_LIST_RAISE = 66           # the list is moved up by this many pixels, to leave room for a bigger LCARS_CONTACT_BLOCK_GAP
LCARS_CONTACT_LINE_HEIGHT = 27          # each aircraft takes three lines of this height...
LCARS_CONTACT_RULE_COLOUR = "LIGHT_GREY"    # a line is drawn between the aircraft in that list, in this colour...
LCARS_CONTACT_RULE_HEIGHT = 2           # ...and this many pixels thick
LCARS_CONTACT_BLOCK_GAP = 12            # ...and then this much space before the next aircraft
LCARS_FLASH_SECONDS = 4                 # a new contact blinks white in the list and on the radar for this long...
LCARS_FLASH_BLINKS_PER_SECOND = 3       # ...at this rate
LCARS_EVENT_MAX_NAMES = 2               # more contacts than this arriving (or leaving) together are announced as a number
LCARS_SEARCH_TITLE_NO_CONTACTS = "No contacts in range"     # the title of the animation shown instead of an empty list...
LCARS_SEARCH_TITLE_NO_SIGNAL = "No signal from receiver"    # ...or, if the last fetch of the aircraft failed, this

# --- Emergencies, military and emergency services aircraft ----------

LCARS_POPUP_CENTRE_Y = 230              # where the middle of the popup is, from the top of the screen: it is 324 high, so this keeps it above the radar
LCARS_POPUP_SECONDS = 15                # an emergency's popup stays up this long...
LCARS_POPUP_BEEP_SECONDS = 4            # ...and its alarm sounds again this often meanwhile
LCARS_MILITARY_MARKER_COLOUR = "WHITE"  # the brackets round a military aircraft
LCARS_SERVICE_MARKER_COLOUR = "BUTTERSCOTCH"    # the diamond round an emergency services aircraft (police, coastguard...)
LCARS_SERVICE_COLOUR = (80, 230, 120)   # ...and the aircraft itself, on the radar and in the list (a green, which no other aircraft is)


##==================================================================
## LCARS SCREEN: SOUND (lcars_frame/lcars_sound.py)
#
# The alerts' beeps (each of them is set in lcars_sound.py).
##==================================================================

LCARS_SOUND_VOLUME = 0.9                # 0 to 1


##==================================================================
## LCARS SCREEN: HOW ITS PARTS MOVE AND LOOK (lcars_frame/lcars_shapes.py)
#
# The scrolling text, the twinkling lights, the graphs, the radar, the cascading numbers,
# the searching animation and the popup.
##==================================================================

# TextScroller tuning
SHAPES_SCROLL_HOLD = 4.5       # seconds each string is held still
SHAPES_SCROLL_SPEED = 120      # scroll rate in pixels per second
SHAPES_SCROLL_PAD = 10         # inset from the left/right edges of the box
SHAPES_SCROLL_MAX_MESSAGES = 4 # most messages (see TextScroller.message) that can be waiting their turn

# Ticker tuning
SHAPES_TICKER_SPEED = 100                  # scroll rate in pixels per second
SHAPES_TICKER_SEPARATOR = "   \u2022   "   # bullet shown between strings

# Twinkler tuning - seconds between colour changes at each rate.
SHAPES_TWINKLE_FAST = 0.3   
SHAPES_TWINKLE_MEDIUM = 0.8
SHAPES_TWINKLE_SLOW = 2     
SHAPES_TWINKLE_VERYSLOW = 10
SHAPES_TWINKLE_SPREAD = 0.7    # random rates vary +/- this fraction of the period

# Graph tuning - the most of each value's slice of the x axis that a bar fills
# (the rest is the gap between bars). A bar is always at least 1 pixel wide.
SHAPES_GRAPH_BAR_FRACTION = 2 / 3

# Graph tuning - the white dot on the current hour swells and shrinks between these two
# radii (in pixels), once every SHAPES_GRAPH_PULSE_SECONDS
SHAPES_GRAPH_DOT_MIN = 4
SHAPES_GRAPH_DOT_MAX = 7
SHAPES_GRAPH_PULSE_SECONDS = 1.6

SHAPES_BAR_TEXT_PAD = 8                # space between the edge of a Bar and its text, in pixels

# Radar tuning - the space left around the circle for the ring of ticks and the N, E, S and W tabs
SHAPES_RADAR_MARGIN = 22
SHAPES_RADAR_TAB_SIZE = 18             # width and height of those tabs
SHAPES_RADAR_TICK_DEGREES = 10         # a tick on the ring every this many degrees...
SHAPES_RADAR_LONG_TICK_DEGREES = 30    # ...and a longer one every this many
SHAPES_RADAR_SWEEP_SECONDS = 6         # how long the sweep takes to go once round
SHAPES_RADAR_SWEEP_GLOW_DEGREES = 50   # how far behind the sweep line its glow reaches
SHAPES_RADAR_SWEEP_GLOW_ALPHA = 90     # how strong the glow is next to the line (0 to 255)
SHAPES_RADAR_FLARE_DEGREES = 120       # an aircraft lights up as the sweep passes it, and fades over this many degrees...
SHAPES_RADAR_FLARE_AMOUNT = 0.7        # ...going this fraction of the way towards white at its brightest
SHAPES_RADAR_MARKER_GAP = 5            # a marker round an aircraft (see drawMarker) is this many pixels outside its icon
SHAPES_RADAR_LABEL_GAP = 6               # extra space between an aircraft's icon and its number on the radar, in pixels

# Cascade tuning - every SHAPES_CASCADE_INTERVAL seconds, SHAPES_CASCADE_CHANGES of its numbers change
SHAPES_CASCADE_INTERVAL = 0.12
SHAPES_CASCADE_CHANGES = 3
SHAPES_CASCADE_PAD = 4                 # space to the left of each number, in pixels

# Searching tuning - the animation for an empty list: rows of segments with a light bouncing along each
SHAPES_SEARCH_ROWS = 4
SHAPES_SEARCH_SEGMENTS = 22            # segments in each row
SHAPES_SEARCH_GAP = 5                  # pixels between segments, and between rows
SHAPES_SEARCH_TRAIL = 7                # how many segments the glow behind each light reaches
SHAPES_SEARCH_MIN_SPEED = 4            # slowest and fastest row, in segments per second
SHAPES_SEARCH_MAX_SPEED = 12
SHAPES_SEARCH_UNLIT = 0.9             # how far the unlit segments are faded towards the background (0 to 1)
SHAPES_SEARCH_HEAD_WHITE = 0.6         # how far the light itself is taken towards white (0 to 1)
SHAPES_SEARCH_DOT_SECONDS = 0.5        # seconds between the dots after SCANNING
SHAPES_SEARCH_TITLE_HEIGHT = 100       # the space for the title, and under it for SCANNING, in pixels
SHAPES_SEARCH_SUBTITLE_HEIGHT = 80

# Popup tuning
SHAPES_POPUP_WIDTH = 1000
SHAPES_POPUP_FRAME = 8                 # thickness of the frame, in pixels
SHAPES_POPUP_RADIUS = 28               # how round its corners are
SHAPES_POPUP_TITLE_HEIGHT = 64
SHAPES_POPUP_BAND_HEIGHTS = (110, 60, 44)      # the heights of the three lines of text under the title
SHAPES_POPUP_PAD = 30                  # space left of the text, and below the last line
SHAPES_POPUP_FLASH_HZ = 2              # how many times a second the colours flash

# Meter tuning - how dark the unlit segments are, as a fraction of the colour
SHAPES_METER_DIM = 0.22

# Text switches from white to black once the shape behind it is this bright
SHAPES_TEXT_CONTRAST_THRESHOLD = 160

# How big each kind of aircraft is drawn on the radar, compared with the size asked for: heavy
# aircraft are bigger and light ones smaller (a kind that isn't here is drawn at that size)
SHAPES_ICON_SCALES = {"LIGHT": 0.75, "SMALL": 0.85, "HEAVY": 1.25, "FAST": 0.9, "HELICOPTER": 0.9}
SHAPES_HELICOPTER_SPIN = 720           # degrees per second, for a helicopter's rotor


##==================================================================
## LCARS SCREEN: THE WEATHER FORECAST (lcars_frame/lcars_weather.py)
#
# Fetched from Open-Meteo, for WEATHER_LAT and WEATHER_LON (in my_settings.py).
##==================================================================

WEATHER_FORECAST_DAYS = 5

WEATHER_UPDATE_INTERVAL = 30 * 60   # seconds between successful updates (=30 minutes)
WEATHER_RETRY_INTERVAL = 5 * 60     # seconds before retrying after a failure
WEATHER_REQUEST_TIMEOUT = 10        # seconds

WEATHER_DEBUG = False               # print the request URL on every fetch


##==================================================================
## LCARS SCREEN: THE AIRCRAFT (lcars_frame/aircraft.py)
#
# Read from your ADS-B receiver at AIRCRAFT_URL, and measured from HOME_LAT and HOME_LON
# (all in my_settings.py).
##==================================================================

AIRCRAFT_POLL_SECONDS = 3
AIRCRAFT_RADIUS_NM = 15              # only aircraft this close (nautical miles) are kept
AIRCRAFT_SERVICE_RADIUS_NM = 3        # an emergency services aircraft is only announced this close (nautical miles); it is coloured at any range
AIRCRAFT_MAX_ALTITUDE_FT = 99999     # ...and only if they are lower than this (feet)
AIRCRAFT_MAX_POSITION_AGE_SECS = 180 # ...and only if their position is this fresh
AIRCRAFT_TRAIL_SECONDS = 900         # how far back an aircraft's trail goes


##==================================================================
## LCARS SCREEN: EACH AIRCRAFT'S ROUTE AND MODEL (lcars_frame/lookups.py)
#
# Looked up on adsbdb.com.
##==================================================================

LOOKUP_FOUND_EXPIRY_SECS = 6 * 60 * 60     # a good answer is looked up again after this long
LOOKUP_MISSING_EXPIRY_SECS = 5 * 60        # ...and a missing one, after this long
LOOKUP_TIMEOUT_SECS = 10
LOOKUP_RETRY_EXPIRY_SECS = 30               # a lookup that couldn't reach the service is tried again after this long
LOOKUP_HOME_AIRPORT = "MAN"                # routes are only shown for flights to or from this airport (its code)
LOOKUP_PAUSE_SECS = 0.5             # each lookup thread waits this long between lookups
LOOKUP_BACKOFF_SECS = 60                   # after a 429, all lookups stop for this long (or as long as the service says)...
LOOKUP_BACKOFF_MAX_SECS = 30 * 60          # ...doubling each time it happens again, up to this, until a lookup works


##==================================================================
## LCARS SCREEN: THE CALENDAR (lcars_frame/lcars_calendar.py)
#
# Your next Google Calendar events, in the Captain's Log.
##==================================================================

CALENDAR_ID = "primary"

# Google can return a short page of events even when there are more, so the
# fetch asks for further pages until it has enough. This stops it asking
# forever if Google keeps sending short or empty pages.
CALENDAR_MAX_PAGES = 10

CALENDAR_DEBUG = False       # print how many events, and how many pages, each fetch gets


##==================================================================
## DEPARTURES BOARD (departures_frame/departures.py)
#
# The split-flap board of the aircraft overhead.
##==================================================================

# The columns: heading, and how many letters wide
DEPARTURES_COLUMNS = [("FLIGHT", 7), ("FROM", 11), ("TO", 11), ("DISTANCE", 8), ("HEIGHT", 6), ("STATUS", 10)]
DEPARTURES_ROWS = 14

DEPARTURES_TILE_W, DEPARTURES_TILE_H = 30, 50         # each flap, in pixels...
DEPARTURES_TILE_GAP = 3                    # ...the space between them...
DEPARTURES_COLUMN_GAP = 24                 # ...and between the columns
DEPARTURES_ROW_PITCH = 60
DEPARTURES_TOP = 196                       # the top of the first row

DEPARTURES_UPDATE_SECONDS = 10             # the aircraft on the board are brought up to date this often
DEPARTURES_FLIP_SECONDS = 0.045            # how long a flap takes to fall to the next letter
DEPARTURES_START_SPREAD = 0.35             # the flaps start up to this long after one another, as on a real board

# The letters on each flap's drum, in the order it goes round them
DEPARTURES_DRUM = " ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.,-:/'&"

DEPARTURES_BOARD = (16, 16, 18)
DEPARTURES_TEXT = (246, 238, 214)
DEPARTURES_AMBER = (255, 186, 60)
DEPARTURES_GREEN = (120, 225, 120)
DEPARTURES_RED = (255, 80, 64)
DEPARTURES_BLUE = (140, 200, 255)
DEPARTURES_HEADING = (150, 150, 150)

DEPARTURES_CLIMB_FPM = 400                 # climbing or descending faster than this, in feet a minute
DEPARTURES_LOW_FT = 6000                   # below this, a flight from or to our airport is departing or landing


##==================================================================
## DEVIANTART FRAME (deviantart_frame/deviantart_frame.py)
#
# Showing the pictures, and the clock and the credit on them.
##==================================================================

DEVIANTART_PICTURE_SECONDS = 20            # each picture is shown for this long...
DEVIANTART_FADE_SECONDS = 3                # ...and fades into the next over this long

DEVIANTART_DELETED_FOLDER = "deleted"      # your own pictures, when deleted, are moved to this folder inside PICTURE_FOLDER
DEVIANTART_NOTICE_SECONDS = 3              # "PICTURE DELETED" is shown for this long

DEVIANTART_FILL_SCREEN = True              # zoom each picture to fill the screen, cutting off what doesn't fit; False: show all of it
DEVIANTART_WHITE = (255, 255, 255)         # the colour of all the text
DEVIANTART_BACKGROUND = (0, 0, 0)          # round a picture that isn't the shape of the screen (when DEVIANTART_FILL_SCREEN is False)
DEVIANTART_RESCAN_SECONDS = 10             # how often to look in the folder again when it has no pictures
DEVIANTART_ONLINE_FOLDER = "deviantart"    # the downloaded pictures go in this folder inside PICTURE_FOLDER
DEVIANTART_OWN_PICTURES = True             # True: show your own pictures too, mixed in with them...
DEVIANTART_OWN_FOLDER = "my_own"           # ...from this folder inside PICTURE_FOLDER
DEVIANTART_CREDIT_MARGIN = 20              # the credit's distance from the corner of the screen, in pixels
DEVIANTART_CREDIT_PAD = 10                 # the space round its text, inside its dark background
DEVIANTART_CREDIT_BACKGROUND = (0, 0, 0, 150)   # the colour of that background, and how solid it is (0 to 255)
DEVIANTART_CREDIT_COLOUR = DEVIANTART_WHITE
DEVIANTART_CLOCK_MARGIN = 30               # the clock's distance from the top right corner, in pixels
DEVIANTART_CLOCK_PAD = 20                  # the space round its text, inside its dark background
DEVIANTART_CLOCK_BACKGROUND = (0, 0, 0, 150)   # as DEVIANTART_CREDIT_BACKGROUND
DEVIANTART_CLOCK_TIME_FORMAT = "%H:%M:%S"     # the time, in big text...
DEVIANTART_CLOCK_DATE_FORMAT = "%d %B %Y"  # ...and under it the date...
DEVIANTART_CLOCK_DAY_FORMAT = "%A"         # ...and the day of the week (see strftime for what these mean)
DEVIANTART_CLOCK_DATE_SIZE = "LARGE"   # the size of the day and the date (the time is XXL)


##==================================================================
## DEVIANTART FRAME: DOWNLOADING THE PICTURES (deviantart_frame/deviantart_library.py)
#
# How many are fetched each day, and how. Which artists, topics and tags they come from
# is in deviantart_frame/deviantart_choices.txt.
##==================================================================

DOWNLOAD_PICTURE_COUNT = 30              # how many new pictures to fetch each day from the choices...
DOWNLOAD_DAILY_COUNT = 10                # ...and how many of the Daily Deviations as well...
DOWNLOAD_KEEP_COUNT = 400                # ...and how many to keep: the oldest beyond this are deleted
DOWNLOAD_MAX_ZOOM = 1.6                  # pictures that would have to be zoomed more than this to fill the screen
                                         # are low resolution, and passed over (1.2: at least 1600 x 900)
DOWNLOAD_MAX_ORIGINAL_BYTES = 25_000_000 # a downloadable original bigger than this is too slow to show
DOWNLOAD_DAILY_DAYS = 7                  # Daily Deviations: today's and this many days before (enough
                                         # to find DOWNLOAD_DAILY_COUNT that are wide and big enough)...
DOWNLOAD_POPULAR_TIMERANGE = "1week"     # ...then the most popular of this long ("1week", "1month", "alltime")
DOWNLOAD_PAGE_SIZE = 24                  # pictures are asked for this many at a time (24 is the most allowed)...
DOWNLOAD_MAX_PAGES = 5                   # ...for at most this many pages from each artist, topic, tag or popular
DOWNLOAD_SEEN_LIMIT = 5000               # how many fetched pictures to remember

DOWNLOAD_CHECK_INTERVAL = 10 * 60        # seconds between checks for a new day
DOWNLOAD_RETRY_INTERVAL = 30 * 60        # seconds before trying again after a failure
DOWNLOAD_REQUEST_TIMEOUT = 30            # seconds
DOWNLOAD_REQUEST_PAUSE = 1               # seconds between requests, to be polite
DOWNLOAD_MAX_TOPIC_PAGES = 30            # most pages of topics "topics" will ask for (10 a page)


##==================================================================
## BIOMONITOR (biomonitor_frame/biomonitor.py)
#
# The sickbay biomonitor's dials and lamps.
##==================================================================

BIOMONITOR_FONT_SIZE_1 = 22
BIOMONITOR_FONT_SIZE_2 = 28

BIOMONITOR_DIAL_TOP = 100
BIOMONITOR_DIAL_HEIGHT = 800

BIOMONITOR_DIAL_MARGIN = 170
BIOMONITOR_DIAL_SPACING = 270

BIOMONITOR_RESPIRATION_RATE = 18       # flashes a minute of the breathing lamp...
BIOMONITOR_PULSE_RATE = 72             # ...and of the pulse lamp

BIOMONITOR_BACKGROUND_COLOUR = (10, 10, 10)
BIOMONITOR_BLACK = BIOMONITOR_BACKGROUND_COLOUR
BIOMONITOR_WHITE = (255, 255, 255)
BIOMONITOR_RED = (255, 50, 50)
BIOMONITOR_YELLOW = (180, 150, 50)
BIOMONITOR_GREEN = (100, 255, 100)
BIOMONITOR_LAMP_COLOUR = (220, 50, 50)
BIOMONITOR_GAMMA = 3.5


##==================================================================
## CLOCK SCREEN (clock_frame/clock.py)
#
# Which faces the OK button goes round, the chimes and ticks, and the quiet hours.
##==================================================================

# --- The faces ------------------------------------------------------

# The faces, in the order the OK button goes round them. The first is shown when the program
# starts. Leave out any you don't want.
CLOCK_FACES = ["BRASS", "RAILWAY", "DECO", "NIXIE", "FLIP"]

# --- Sound ----------------------------------------------------------

CLOCK_CHIME = True                  # False: start with no chimes, strikes or pips, on any face (holding SOUND turns them on)...
CLOCK_TICK = True                   # ...or no ticks (or clunks, or clacks)
CLOCK_CHIME_WHEN_HIDDEN = True      # True: chime even while another screen is shown (ticks are only heard on this one)
CLOCK_CHIME_VOLUME = 0.6            # 0 to 1: the chimes are always this loud (the SOUND button doesn't change them)
CLOCK_TICK_LOUDNESS = 0.25          # the ticks at HIGH are this much of the chimes' loudness (12 dB quieter)

# On the clock, the SOUND button sets only how loud the ticks are, going round these levels:
# (name, how loud, compared with HIGH). Holding it down turns the chimes off, or back on.
CLOCK_TICK_VOLUMES = [("OFF", 0.0), ("LOWER", 0.125), ("LOW", 0.25), ("MEDIUM", 0.5), ("HIGH", 1.0)]
CLOCK_TICK_VOLUME_ORDER = [1, 2, 3, 4, 0]   # lower, low, medium, high, off, and round again (it starts at high)

# --- Quiet hours (the aquarium dims its light then too) ------------

CLOCK_QUIET_FROM = 0                # no ticks or chimes from this hour (0 is midnight)...
CLOCK_QUIET_UNTIL = 9               # ...until this one, so the 9 o'clock chime is the first of the day

# --- Notices --------------------------------------------------------

CLOCK_STATUS_CORNER = (1890, 1050)  # the bottom right corner of the notice that the clock is silent at night
CLOCK_NOTICE_SECONDS = 2.0          # how long the name of the face is shown when OK changes it
CLOCK_NOTICE_COLOUR = (204, 153, 204)


##==================================================================
## CLOCK: BRASS FACE (clock_frame/brass.py)
##==================================================================

# --- What it does ---------------------------------------------------

BRASS_MOTTO = "Tempus Fugit"        # written on the dial...
BRASS_EVENING_MOTTO = "Beer O'Clock"    # ...or this, from BRASS_EVENING_FROM until midnight
BRASS_EVENING_FROM = 22
BRASS_SECOND_SETTLE = 0.3           # seconds the seconds hand takes to jump to the next second and settle

# --- Sound ----------------------------------------------------------

BRASS_STRIKE_HOURS = True           # after the hour's Westminster chime, strike the hour (once for one o'clock...)

# --- Where and how big ----------------------------------------------

BRASS_CLOCK_RADIUS = 500            # the outside of the brass case
BRASS_CLOCK_CENTRE = (960, 540)

# These are fractions of BRASS_CLOCK_RADIUS, so that they grow and shrink with the clock
BRASS_MOON_WINDOW_Y = 0.17          # the moon window: its flat side this far above the middle...
BRASS_MOON_WINDOW_RADIUS = 0.24     # ...and this wide
BRASS_CALENDAR_WINDOWS = [("%a", 0.17), ("%d", 0.12), ("%b", 0.17)]    # the calendar windows: (what strftime shows, how wide)
BRASS_CALENDAR_HEIGHT = 0.09
BRASS_CALENDAR_Y = 0.25             # how far below the middle the calendar is...
BRASS_MOTTO_Y = 0.39                # ...and the motto
BRASS_HOUR_LENGTH = 0.50            # the hands, from the middle
BRASS_MINUTE_LENGTH = 0.76
BRASS_SECOND_LENGTH = 0.80
BRASS_SECOND_TAIL = 0.20            # the seconds hand's tail, behind the middle

# --- Colours --------------------------------------------------------

BRASS_INK = (32, 27, 22)            # the numerals and the lines on the dial
BRASS_BRASS = (196, 152, 74)
BRASS_STEEL = (16, 20, 44)          # the blued steel of the hands...
BRASS_STEEL_LIGHT = (48, 62, 118)   # ...and its lit side
BRASS_TEXT_COLOUR = (222, 186, 112) # the notice in the corner at night
BRASS_CARD = (243, 236, 220)        # the calendar wheels seen through their windows
BRASS_SKY = (20, 36, 92)            # the moon disc's night sky
BRASS_MOON = (232, 206, 140)        # its painted gold moons


##==================================================================
## CLOCK: RAILWAY FACE (clock_frame/railway.py)
##==================================================================

# --- What it does ---------------------------------------------------

RAILWAY_SWEEP_SECONDS = 58.5        # the seconds hand goes round in this long, then waits at the top for
                                    # the minute to begin, as a station clock waits for the master clock
                                    # (60: no wait)
RAILWAY_MINUTE_SETTLE = 0.25        # seconds the minute hand takes to jump and settle

# --- Sound ----------------------------------------------------------

RAILWAY_HOURLY_CHIME = True         # a station chime on the hour (the minute hand's clunk is a tick)

# --- Where and how big ----------------------------------------------

RAILWAY_CLOCK_RADIUS = 480
RAILWAY_CLOCK_CENTRE = (960, 565)
RAILWAY_DADO_Y = 790                # the line between the cream wall and the green below

# --- Colours --------------------------------------------------------

RAILWAY_DIAL = (246, 246, 242)
RAILWAY_INK = (18, 18, 18)          # the bars on the dial and the hands...
RAILWAY_INK_LIGHT = (40, 40, 40)    # ...and the hands' lit side
RAILWAY_RED = (204, 26, 22)         # the seconds hand...
RAILWAY_RED_LIGHT = (226, 48, 40)   # ...and its lit side
RAILWAY_CASE = (58, 60, 64)         # the case and the rod it hangs from
RAILWAY_WALL_UPPER = (214, 204, 176)    # cream paint above the dado line...
RAILWAY_WALL_LOWER = (34, 72, 52)   # ...and green below
RAILWAY_DADO = (98, 22, 24)         # the line between them
RAILWAY_TEXT_COLOUR = (226, 216, 186)   # the notice in the corner at night


##==================================================================
## CLOCK: DECO FACE (clock_frame/deco.py)
##==================================================================

# --- What it does ---------------------------------------------------

DECO_BEATS = 3                      # the seconds hand moves (and ticks) this many times a second

# --- Sound ----------------------------------------------------------

DECO_STRIKE_HOURS = True            # after the hour's ding-dongs, strike the hour on the gong

# --- Where and how big ----------------------------------------------

DECO_CENTRE = (960, 468)            # the middle of the dial
DECO_DIAL_RADIUS = 330
DECO_RADIUS = 400                   # the outside of the chrome bezel
DECO_BODY_RADIUS = 452              # the round black body behind the bezel
DECO_MANTEL_Y = 1000                # the top of the mantelpiece

# The case below the round body: (half its width, its top, its bottom, its corners, chrome?)
DECO_BLOCKS = [
    (520, 690, 905, 34, False),
    (565, 900, 930, 10, True),
    (605, 926, DECO_MANTEL_Y, 14, False),
]
DECO_SPEED_LINES = [742, 768, 794]  # thin chrome lines across the case, at these heights...
DECO_SPEED_LINE_HALF = 470          # ...and this long either side of the middle

# --- Colours --------------------------------------------------------

DECO_LACQUER = (14, 14, 17)         # the case
DECO_CHROME = (232, 236, 244)
DECO_CHAMPAGNE = (224, 202, 152)    # the dial
DECO_INK = (20, 18, 16)             # the numerals and marks on it
DECO_HAND = (14, 14, 16)            # the hands...
DECO_HAND_LIGHT = (58, 58, 64)      # ...and their lit side
DECO_WALL = (24, 50, 44)            # the wallpaper...
DECO_GOLD = (190, 156, 86)          # ...its fans (and the notice in the corner at night)
DECO_MARBLE = (226, 222, 214)       # the mantelpiece...
DECO_VEIN = (150, 146, 140)         # ...and its veins


##==================================================================
## CLOCK: NIXIE FACE (clock_frame/nixie.py)
##==================================================================

# --- What it does ---------------------------------------------------

NIXIE_HOURS_24 = True               # False: 1 to 12, with no leading zero
NIXIE_ROLL_MINUTES = 15             # the tubes run through their digits at each quarter (0: never)...
NIXIE_ROLL_SECONDS = 2.2            # ...for this long
NIXIE_FADE_SECONDS = 0.22           # one digit fading into the next

# --- Sound ----------------------------------------------------------

NIXIE_PIPS = True                   # the time pips before each hour: five short and a long one on the hour
NIXIE_PIP_LOUDNESS = 0.35           # the pips are this much of the chimes' volume

# --- Where and how big ----------------------------------------------

NIXIE_TUBE_W, NIXIE_TUBE_H = 222, 540   # the glass of each tube
NIXIE_PAIR_GAP = 22                 # between the two tubes of the hours (or minutes, or seconds)...
NIXIE_COLON_GAP = 100               # ...and between the pairs, where the dots are
NIXIE_BASE_TOP, NIXIE_BASE_BOTTOM = 726, 880    # the walnut base
NIXIE_SOCKET_H = 34                 # the black sockets the tubes stand in
NIXIE_DIGIT_HALF_W, NIXIE_DIGIT_HALF_H = 82, 150    # half the size of the digits
NIXIE_DIGIT_Y = 0.55                # the middle of the digits, as a fraction of the tube's height from its top

# --- Colours --------------------------------------------------------

NIXIE_NEON = (255, 96, 14)          # the glow...
NIXIE_NEON_CORE = (255, 196, 120)   # ...and the bright wire in it
NIXIE_WIRE = (66, 60, 54)           # the digits that are not lit
NIXIE_WALNUT = (96, 54, 30)
NIXIE_PLATE = (186, 150, 82)        # the brass plate with the date
NIXIE_TEXT_COLOUR = (255, 140, 60)  # the notice in the corner at night


##==================================================================
## CLOCK: FLIP FACE (clock_frame/flip.py)
##==================================================================

# --- What it does ---------------------------------------------------

FLIP_HOURS_24 = True                # False: 1 to 12
FLIP_SECONDS = 0.32                 # how long a card takes to fall (it clacks as it lands: a tick)

# --- Where and how big ----------------------------------------------

FLIP_BIG_W, FLIP_BIG_H, FLIP_BIG_GAP = 600, 620, 56     # the hours and the minutes
FLIP_SMALL_H, FLIP_SMALL_GAP = 120, 24  # the day, the date and the month...
FLIP_SMALL_WIDTHS = [230, 150, 230]
FLIP_ROW_GAP = 34                   # ...below the big cards, this far
FLIP_MARGIN = 44                    # round the cards, inside the black window
FLIP_CASE_EDGE = 58                 # the plastic round the window
FLIP_TOP = 54                       # the top of the case
FLIP_CORNER = 26                    # the corners of the cards

# --- Colours --------------------------------------------------------

FLIP_CARD = (34, 34, 37)
FLIP_DIGITS = (238, 234, 222)
FLIP_RECESS = (12, 12, 13)          # the black window the cards are in
FLIP_CASE = (234, 230, 220)
FLIP_TEAK = (118, 66, 34)           # the sideboard
FLIP_TEXT_COLOUR = (240, 200, 140)  # the notice in the corner at night


##==================================================================
## AQUARIUM (aquarium_frame/aquarium.py)
#
# The fish tank. At night (the clock's quiet hours, CLOCK_QUIET_FROM) its light goes down.
##==================================================================

AQUARIUM_SOUND = True
AQUARIUM_SOUND_VOLUME = 0.075            # 0 to 1

AQUARIUM_SAND_TOP = 880                  # the top of the sand
AQUARIUM_SURFACE = 40                    # the bottom of the water's surface
AQUARIUM_TAIL_FRAMES = 8                 # pictures of each fish, its tail in a different place in each
AQUARIUM_FOOD_FLAKES = 14                # flakes in each sprinkle of food

# The fish: (kind, how many, length in pixels)
AQUARIUM_STOCK = [("tetra", 14, 56), ("clown", 3, 118), ("blue tang", 2, 170), ("yellow tang", 2, 136),
                  ("angel", 2, 140), ("goldfish", 2, 128)]

# How each kind looks:
#   colour, belly   the colour of its back and sides, and of its belly
#   tall            how tall its body is for its length
#   tail            "fork", "round" or "long" (flowing, like a goldfish's)
#   fin, edge       the colour of its fins, and of their edges (or None)
#   eye             the colour of the ring round the pupil
#   bands           upright bands of (from, to, colour), measured from the tail (0) to the nose (1)
#   stripes         lengthwise stripes of (from, to, top, bottom, colour), top and bottom from -1
#                   (the back) to 1 (the belly)
#   speed           how fast it swims, in pixels a second
AQUARIUM_KINDS = {
    "clown": dict(colour=(244, 104, 20), belly=(252, 150, 60), tall=0.5, tail="round", fin=(244, 110, 30),
                  edge=(24, 18, 16), eye=(200, 90, 20),
                  bands=[(0.12, 0.2, (250, 250, 245)), (0.46, 0.57, (250, 250, 245)), (0.78, 0.86, (250, 250, 245))],
                  speed=60),
    "blue tang": dict(colour=(30, 84, 200), belly=(70, 140, 230), tall=0.62, tail="fork", tailColour=(250, 206, 36),
                      fin=(30, 84, 200), edge=(12, 16, 40), eye=(30, 30, 50),
                      stripes=[(0.22, 0.86, -0.8, -0.2, (14, 18, 40))], speed=80),
    "yellow tang": dict(colour=(250, 208, 30), belly=(255, 232, 110), tall=0.82, tail="fork", fin=(250, 208, 30),
                        edge=None, eye=(40, 40, 40), speed=70, snout=True),
    "tetra": dict(colour=(150, 170, 160), belly=(225, 228, 232), tall=0.34, tail="fork", fin=(210, 220, 230),
                  edge=None, eye=(200, 200, 210),
                  stripes=[(0.15, 0.92, -0.42, -0.08, (40, 190, 255)), (0.08, 0.55, 0.05, 0.9, (232, 40, 50))],
                  speed=95),
    "angel": dict(colour=(196, 198, 190), belly=(238, 238, 230), tall=0.95, tail="fork", fin=(220, 222, 214),
                  edge=(40, 40, 40), eye=(190, 40, 30),
                  bands=[(0.25, 0.3, (40, 40, 40)), (0.55, 0.61, (40, 40, 40)), (0.82, 0.86, (60, 60, 60))],
                  bigFins=True, speed=45),
    "goldfish": dict(colour=(240, 130, 20), belly=(255, 196, 90), tall=0.52, tail="long", fin=(250, 160, 60),
                     edge=None, eye=(180, 120, 40), speed=50),
}

AQUARIUM_WATER_TOP = (48, 150, 176)
AQUARIUM_WATER_BOTTOM = (8, 44, 84)
AQUARIUM_NIGHT = (70, 84, 130)           # the tank at night is lit this much (multiplied)


##==================================================================
## VIEWSCREEN (viewscreen_frame/viewscreen.py)
#
# The bridge's main viewscreen, its stars, and its jumps to warp.
##==================================================================

VIEWSCREEN_SOUND = True
VIEWSCREEN_SOUND_VOLUME = 0.5              # 0 to 1
VIEWSCREEN_AUTO_WARP_MINUTES = (3, 7)      # at impulse, it goes to warp by itself after between these many minutes (None: only with OK)
VIEWSCREEN_WARP_SECONDS = (12, 30)         # and stays at warp for between these many seconds

VIEWSCREEN_VIEW = (150, 64, 1620, 800)     # the screen itself, inside its frame
VIEWSCREEN_CORNER = 46                     # how round its corners are
VIEWSCREEN_BEZEL = 30                      # how wide the metal frame round it is

VIEWSCREEN_STARS = 650
VIEWSCREEN_FOCAL = 640                     # how far the stars are spread: bigger looks more zoomed in
VIEWSCREEN_IMPULSE_SPEED = 0.025           # how fast the stars come towards you, in their units a second...
VIEWSCREEN_WARP_SPEED = 2.2                # ...and at warp
VIEWSCREEN_ENGAGE_SECONDS = 1.6            # the stars stretch for this long before the jump to warp
VIEWSCREEN_DROP_SECONDS = 1.1              # and slow for this long when dropping out of warp

VIEWSCREEN_ORANGE = (255, 153, 0)
VIEWSCREEN_PEACH = (255, 160, 90)
VIEWSCREEN_LILAC = (204, 153, 255)
VIEWSCREEN_ICE_BLUE = (153, 204, 255)
VIEWSCREEN_BUTTERSCOTCH = (255, 204, 102)
VIEWSCREEN_BLUE = (132, 132, 255)
VIEWSCREEN_AMBER_LIGHT = (255, 170, 60)    # the running lights at impulse...
VIEWSCREEN_BLUE_LIGHT = (110, 175, 255)    # ...and at warp
VIEWSCREEN_CHIRP_SECONDS = (5, 16)         # the consoles chirp every so often, between these many seconds apart


##==================================================================
## YOUR OWN SETTINGS (my_settings.py)
#
# Where you are and your aircraft receiver: HOME_LAT, HOME_LON, WEATHER_LAT, WEATHER_LON and
# AIRCRAFT_URL. Copy my_settings_example.py to my_settings.py and put your own in it. Until
# then, the made-up ones in my_settings_example.py are used. Anything else set in it replaces
# the setting above.
##==================================================================

try:
    from my_settings import *               # noqa: F401,F403
except ImportError:
    print("No my_settings.py, so using the made-up settings in my_settings_example.py")
    from my_settings_example import *       # noqa: F401,F403
