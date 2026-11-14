# lcars_screen.py
#
# The LCARS screen: an ambient Star Trek style screen built from the shapes in lcars_shapes.py.
# Nothing to interact with - it just sits there looking busy.
#
# It is one of several screens (see screens.py), started by lcars2.py. Everything it
# uses is in this folder.

#Windows: pip install psutil
#Raspberry Pi OS: sudo apt install python3-psutil.

import math
import operator
import os
import random
import time
import traceback
import pygame
import psutil
import fonts
import screens as scr
from . import lcars_shapes as ls
from . import lcars_weather as lw
from . import lcars_calendar as lc
from . import aircraft as ac
from . import lookups as lk
from . import lcars_sound as sound
from . import weather_data as wd
from datetime import datetime


# Its settings are in settings.py (next to lcars.py)
from settings import (
    LCARS_CPU_RATE as CPU_RATE,
    LCARS_BORDER as BORDER,
    LCARS_DIMMED as DIMMED,
    LCARS_LIGHTER as LIGHTER,
    LCARS_GRAPH_DAYS as GRAPH_DAYS,
    LCARS_FORECAST_COUNT as FORECAST_COUNT,
    LCARS_FORECAST_STEP_HOURS as FORECAST_STEP_HOURS,
    LCARS_CALENDAR_EVENT_COUNT as CALENDAR_EVENT_COUNT,
    LCARS_CALENDAR_COLUMN_GAP as CALENDAR_COLUMN_GAP,
    LCARS_WEATHER_STALE_SECONDS as WEATHER_STALE_SECONDS,
    LCARS_GRAPH_WIDTH as GRAPH_WIDTH,
    LCARS_GRAPH_GAP as GRAPH_GAP,
    LCARS_RADAR_SIZE as RADAR_SIZE,
    LCARS_RADAR_RING_NM as RADAR_RING_NM,
    LCARS_RADAR_ICON_BIG as RADAR_ICON_BIG,
    LCARS_RADAR_ICON_SMALL as RADAR_ICON_SMALL,
    LCARS_RADAR_ALTITUDE_MAX_FT as RADAR_ALTITUDE_MAX_FT,
    LCARS_RADAR_PASSING_FT as RADAR_PASSING_FT,
    LCARS_RADAR_ICON_PASSING as RADAR_ICON_PASSING,
    LCARS_AIRPORT_NAME as AIRPORT_NAME,
    LCARS_AIRPORT_LAT as AIRPORT_LAT,
    LCARS_AIRPORT_LON as AIRPORT_LON,
    LCARS_AIRPORT_RUNWAYS as AIRPORT_RUNWAYS,
    LCARS_LIST_NM_PER_1000_FT as LIST_NM_PER_1000_FT,
    LCARS_CONTACT_COUNT as CONTACT_COUNT,
    LCARS_CONTACT_TEXT_SIZE as CONTACT_TEXT_SIZE,
    LCARS_CONTACT_COLUMN_GAP as CONTACT_COLUMN_GAP,
    LCARS_CONTACT_LINE_1_GAP as CONTACT_LINE_1_GAP,
    LCARS_CONTACT_LIST_RAISE as CONTACT_LIST_RAISE,
    LCARS_CONTACT_LINE_HEIGHT as CONTACT_LINE_HEIGHT,
    LCARS_CONTACT_RULE_COLOUR as CONTACT_RULE_COLOUR,
    LCARS_CONTACT_RULE_HEIGHT as CONTACT_RULE_HEIGHT,
    LCARS_CONTACT_BLOCK_GAP as CONTACT_BLOCK_GAP,
    LCARS_POPUP_CENTRE_Y as POPUP_CENTRE_Y,
    LCARS_POPUP_SECONDS as POPUP_SECONDS,
    LCARS_POPUP_BEEP_SECONDS as POPUP_BEEP_SECONDS,
    LCARS_MILITARY_MARKER_COLOUR as MILITARY_MARKER_COLOUR,
    LCARS_SERVICE_MARKER_COLOUR as SERVICE_MARKER_COLOUR,
    LCARS_SERVICE_COLOUR as SERVICE_COLOUR,
    LCARS_SEARCH_TITLE_NO_CONTACTS as SEARCH_TITLE_NO_CONTACTS,
    LCARS_SEARCH_TITLE_NO_SIGNAL as SEARCH_TITLE_NO_SIGNAL,
    LCARS_RADAR_CLIMB_COLOURS as RADAR_CLIMB_COLOURS,
    LCARS_RADAR_DESCEND_COLOURS as RADAR_DESCEND_COLOURS,
    LCARS_RADAR_VERTICAL_FPM as RADAR_VERTICAL_FPM,
    LCARS_RADAR_PROJECT_SECONDS as RADAR_PROJECT_SECONDS,
    LCARS_FLASH_SECONDS as FLASH_SECONDS,
    LCARS_FLASH_BLINKS_PER_SECOND as FLASH_BLINKS_PER_SECOND,
    LCARS_EVENT_MAX_NAMES as EVENT_MAX_NAMES,
    LCARS_HEADER_LEFT_END as HEADER_LEFT_END,
    LCARS_RIGHT_AREA_X as RIGHT_AREA_X,
    LCARS_LOG_CHRONO_GAP as LOG_CHRONO_GAP,
    LCARS_ICON_SIZE_SMALL as ICON_SIZE_SMALL,
    LCARS_ICON_SIZE_LARGE as ICON_SIZE_LARGE,
    LCARS_SIDEBAR_LABELS as SIDEBAR_LABELS,
)

# The text size and the colours are named in settings.py: these are the ones they name
CONTACT_TEXT_SIZE = fonts.TextSize[CONTACT_TEXT_SIZE]
CONTACT_RULE_COLOUR = getattr(ls.Colours, CONTACT_RULE_COLOUR)
MILITARY_MARKER_COLOUR = getattr(ls.Colours, MILITARY_MARKER_COLOUR)
SERVICE_MARKER_COLOUR = getattr(ls.Colours, SERVICE_MARKER_COLOUR)
RADAR_CLIMB_COLOURS = tuple(getattr(ls.Colours, name) for name in RADAR_CLIMB_COLOURS)
RADAR_DESCEND_COLOURS = tuple(getattr(ls.Colours, name) for name in RADAR_DESCEND_COLOURS)


# The three lines of each aircraft in that list. Each column is the widest text it
# will hold (the column is sized to fit it), and which side the text is lined up on.
# The second and third lines are indented, to start under the flight.
CONTACT_LINE_1 = (
    ("5", ls.Alignment.LEFT),                  # the number shown beside the aircraft on the radar
    ("BAW1234", ls.Alignment.LEFT),            # flight
    ("G-ABCD", ls.Alignment.LEFT),             # registration (painted on the tail)
    ("TUI Airways", ls.Alignment.LEFT),        # airline (a longer name is cut back to whole words, see shortenWords)
    (None, ls.Alignment.LEFT),                 # model (None: the column takes the rest of the width)
)
CONTACT_LINE_2 = (
    ("9,999 ft", ls.Alignment.RIGHT),          # altitude
    ("000 kt", ls.Alignment.RIGHT),            # speed
    ("359°", ls.Alignment.RIGHT),              # heading (the direction it is flying)
    ("00.0 NM", ls.Alignment.RIGHT),           # distance
    ("7700", ls.Alignment.RIGHT),              # squawk (the transponder code)
)
CONTACT_LINE_3 = (
    (None, ls.Alignment.LEFT),                 # from and to (blank if there is no route to show)
)
CONTACT_LINES = (CONTACT_LINE_1, CONTACT_LINE_2, CONTACT_LINE_3)


HEADER_RIGHT_END = scr.SCREEN_WIDTH - BORDER     # ...and here for the ones on the right
DEG = "\u00B0"

# ---- TEMPORARY TEST CODE: delete this block, TestAircraftFetcher and the "if TEST_AIRCRAFT" in main() when done ----
TEST_AIRCRAFT = False            # True: show the made-up aircraft below instead of the ones the receiver sees
TEST_CYCLE_SECONDS = 100        # the script below repeats every this many seconds
TEST_POLL_SECONDS = 3           # how often the made-up aircraft are "reported", like the real receiver
# One made-up aircraft each: callsign, hex address, category, squawk, military, bearing and distance from
# the receiver at the start, track, speed, altitude, climb rate, and the seconds into the cycle when it
# appears and when it goes. (Only the first few are in the list: the others are only on the radar.) They all fly in a straight line, and start again from the start each cycle.
TEST_PLANES = (
    ("G-ABCD",  "400A01", "A1", "7000", False,  30, 4.0, 180, 100, 1800,  300,   0, 100),   # LIGHT
    ("LOG401",  "400A02", "A2", "2201", False,  95, 6.0, 270, 220, 3500,    0,   0, 100),   # SMALL
    ("BAW123",  "400A03", "A3", "3301", False, 150, 5.0,  20, 250, 5200, -800,   0, 100),   # LARGE
    ("VIR45",   "400A04", "A5", "4402", False, 215, 7.0,  60, 280, 7800, 1500,   0, 100),   # HEAVY
    ("NPAS61",  "400A05", "A7", "7000", False, 290, 3.5,  90,  90, 1200,    0,   0, 100),   # HELICOPTER, POLICE
    ("UNK123",  "400A06", None, "5501", False, 330, 8.0, 150, 150, 4100,    0,   0, 100),   # no category
    ("RRR4521", "43C123", "A6", "7001", True,  120, 1.5, 120, 330, 2500,    0,  15,  75),   # MILITARY, FAST
    ("EXS7MU",  "400A07", "A3", "7700", False, 250, 6.5,  45, 210, 3000, -500,  30,  55),   # EMERGENCY 7700
    ("TOM88",   "400A08", "A3", "7600", False,  70, 7.5, 200, 230, 4500,    0,  55,  80),   # RADIO FAILURE 7600
    ("RYR99X",  "400A09", "A3", "7500", False, 185, 5.5,  10, 240, 3800,    0,  80, 100),   # HIJACK 7500
)
# ---- end of the temporary test code (the rest is below, just before main) ----


# Relative to this script, not the current directory, so it still works when
# started from autostart / systemd with a different working directory.
ICON_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "graphics", "wmo_icons")
DRIZZLE_CODES = (51, 53, 55, 56, 57)   # WMO codes whose icons get strengthened





# A colour moved part of the way towards white, by LIGHTER
def lighter(colour):
    return ls.mixColours(colour, ls.Colours.WHITE, LIGHTER)


shapes = {}             # Dictionary containing each shape's key and shape object
contactTextWidth = {}     # Shape key -> most pixels of text that shape of the aircraft list can hold
logEventTextWidth = 0     # most pixels of text a Captain's Log event can hold (set when it is built)

borderColour1 = lighter(random.choice(ls.Colours.LCARS_COLOURS))
borderColour2 = tuple(int(c * DIMMED) for c in borderColour1) # slightly dimmed colour

sidebarColour1 = lighter(random.choice(ls.Colours.LCARS_COLOURS))
sidebarColour2 = tuple(int(c * DIMMED) for c in sidebarColour1) # slightly dimmed colour


# One of the LCARS colours that is not this one
def differentColour(colour):
    return lighter(random.choice([other for other in ls.Colours.LCARS_COLOURS if lighter(other) != colour]))



# A new colour scheme, in which both colours are different from the ones before. The shapes
# were made in the old colours, so the whole screen has to be built again (see buildInterface).
def chooseColours():
    global borderColour1, borderColour2, sidebarColour1, sidebarColour2

    borderColour1 = differentColour(borderColour1)
    borderColour2 = tuple(int(c * DIMMED) for c in borderColour1)

    sidebarColour1 = differentColour(sidebarColour1)
    sidebarColour2 = tuple(int(c * DIMMED) for c in sidebarColour1)


# Convert a Unix timestamp (seconds since epoch) to a local-time 'HH:MM' string.
def unix_to_hhmm(timestamp):
    if timestamp is None:
        return "--:--"
    return datetime.fromtimestamp(timestamp).strftime("%H:%M")
    
    # or ... return datetime.fromtimestamp(timestamp, ZoneInfo("Europe/London")).strftime("%H:%M")    
    

# Convert a Unix timestamp (seconds since epoch) to day of week string "MON" etc
def unix_to_weekday(timestamp):
    if timestamp is None:
        return "---"
    return datetime.fromtimestamp(timestamp).strftime("%a")
    
    
# Convert a Unix timestamp (seconds since epoch) to a local-time 'YYYY-MM-DD HH:MM:SS' string.
def unix_to_datetime(timestamp):
    if timestamp is None:
        return "----------"
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")

    # or ... return datetime.fromtimestamp(timestamp, ZoneInfo("Europe/London")).strftime("%Y-%m-%d %H:%M:%S")


def memory_usage_mb():
    used = psutil.Process().memory_info().rss
    vm = psutil.virtual_memory()
    return used / 1048576, vm.available / 1048576, vm.total / 1048576

# Convert a duration in seconds (e.g. daylight_duration) to hours to 1dp, e.g. '5.2 Hr'.
# Not a timestamp, so it mustn't go through fromtimestamp().
def seconds_to_hours(secs):
    if secs is None:
        return "-- Hr"
    return f"{secs / 3600:.1f} Hr"


# Index of the first hourly slot after now_ts, clamped to the last slot.
# Hourly precipitation is the total for the hour ENDING at the slot's time
# (see the units in weather_data.py), so this is the slot covering the coming hour.
# `hourly` is a list of HourlyWeather and must not be empty.
def next_hour_index(hourly, now_ts):
    for i, hour in enumerate(hourly):
        if hour.time > now_ts:
            return i

    return len(hourly) - 1



# Preload all the numicons for the WMO weather codes from the specified folder.
# Resize them and tint them: BLEND_RGBA_MAX raises every pixel's RGB to at
# least sidebarColour1 and leaves the alpha alone, so black-on-transparent
# icons come out borderColour1-on-transparent.
def load_icons(iconFolder, iconSizes):

    #iconColour = sidebarColour1
    iconColour = ls.Colours.WHITE
    
    icons = {size: {} for size in iconSizes}
    
    for filename in os.listdir(iconFolder):
        name, ext = os.path.splitext(filename)
        
        if ext.lower() != ".png" or not name.isdigit():
            continue
            
        original = pygame.image.load(os.path.join(iconFolder, filename)).convert_alpha()
        
        for size in iconSizes:
            scaled = pygame.transform.smoothscale(original, (size, size))
            scaled.fill((*iconColour,0), special_flags=pygame.BLEND_RGBA_MAX)
            
            # Make the drizzle show up more
            #Each time you blit the icon onto itself, the alpha builds up: 
            # a pixel at 30% becomes 51%, then 76%. Fully transparent and fully 
            # solid pixels stay the same. Change passes to 1 for a lighter effect
            # or 3 for a stronger one.            
            if (int(name) in DRIZZLE_CODES) and (size < 70):
                scaled.blit(scaled.copy(), (0, 0))
                scaled.blit(scaled.copy(), (0, 0))
                scaled.blit(scaled.copy(), (0, 0))
                    
            icons[size][int(name)] = scaled        
            
    return icons



# Blit one weather icon, or skip it (with a message) if that code's icon
# file wasn't found, rather than crashing on a KeyError.
def getWeatherIcon(size, code):
    
    icon = weatherIcons.get(size, {}).get(code)
    if icon is None:
        print(f"No {size}px icon for WMO code {code}")

    return icon
    



def buildBackground(surface):

    # top left elbow
    y = 150
    shapes["ELBOW_TL"] = ls.ElbowTopLeft(surface, BORDER, BORDER, 300, y, borderColour1, 100, 20)
    y = BORDER + y + 6

    # Left sidebar boxes with labels
    for i, label in enumerate(SIDEBAR_LABELS):
        shapes[f"SIDEBAR_{i}"] = ls.Twinkler(
            ls.Bar(surface, BORDER + 10, y, 120, 55, sidebarColour1, label, ls.Alignment.RIGHT, fonts.TextSize.SMALL),
            sidebarColour2, ls.TwinkleRate.VERYSLOW_RANDOM)
            
        y += 60
     
    
    # top bars
    x = BORDER + 306
    shapes["OPS"] = \
        ls.Bar(surface, x, BORDER, 200, 40, colour=borderColour2, text="OPERATIONS", alignment=ls.Alignment.CENTRE )
                    
    shapes["OPS_DOT"] = ls.Twinkler(
        ls.Dot(surface, x+20, BORDER+20, 15, ls.Colours.WHITE), borderColour2, ls.TwinkleRate.MEDIUM)                  
                 
    x = x + 205
    shapes["TOPBAR1"] = \
        ls.Bar(surface, x, BORDER, 300, 20, colour=borderColour1)
         
    # LCARS status
    x = x + 305
    shapes["LCARS_STATUS"] = \
        ls.TextScroller(surface, x , BORDER, 350, 40, borderColour2, texts=None, textSize=fonts.TextSize.SMALL)
                 
    x = x + 355
    shapes["TOPBAR2"] = \
        ls.Bar(surface, x, BORDER, 470, 20, colour=borderColour1)

    # Stardate
    x = x + 475
    shapes["STARDATE"] = \
        ls.Bar(surface, x, BORDER, scr.SCREEN_WIDTH - BORDER - x, 40, borderColour2, None, ls.Alignment.RIGHT, fonts.TextSize.SMALL)
                 
    # bottom left elbow
    shapes["ELBOW_BL"] = \
        ls.ElbowBottomLeft(surface, BORDER, scr.SCREEN_HEIGHT-BORDER, 360, scr.SCREEN_HEIGHT - y - 10, borderColour1, 100, 20)

    # Bottom Bar
    x = BORDER + 366
    y = scr.SCREEN_HEIGHT - BORDER - 20
    shapes["BOTTOMBAR"] = \
        ls.Bar(surface, x, y, scr.SCREEN_WIDTH - x - 246, 20, colour=borderColour2)
    
    # Unix Time
    x = scr.SCREEN_WIDTH - 240
    y = scr.SCREEN_HEIGHT - BORDER - 40
    shapes["UNIXTIME"] = \
        ls.Bar(surface, x, y, scr.SCREEN_WIDTH - BORDER - x, 40, borderColour1, None, ls.Alignment.RIGHT, fonts.TextSize.SMALL)
                 
    
# A thin line running on to the right from the end of a title's pill (which is
# 40 high), the way a heading is in LCARS. x is the left end of the pill, and the
# line goes from past its right end (pillWidth along) to endX.
def buildHeaderLine(surface, name, x, y, pillWidth, endX):
    shapes[name] = ls.Bar(surface, x + pillWidth + 8, y + 16, endX - (x + pillWidth + 8), 8, borderColour2)


# How wide the Chronometer is: the hour, colon and minute boxes, then the seconds beside them.
# The boxes are as wide as the digits are in the current font (see buildChronometer).
def chronometerWidth():
    font = fonts.fontFor(fonts.TextSize.XXL)
    digitsWidth = max(font.size(digit * 2)[0] for digit in "0123456789") + 2 * ls.BAR_TEXT_PAD
    colonWidth = font.size(":")[0] + 2 * ls.BAR_TEXT_PAD
    return 2 * digitsWidth + colonWidth + 5 + 100


def buildChronometer(surface, x, y):

    # Coordinates of top left corner. Everything is relative to this
    left = x
    shapes["CHRONO_TITLE"] = ls.Pill(surface, x, y, 200, 40, borderColour1, "CHRONOMETER", ls.Alignment.CENTRE, fonts.TextSize.MEDIUM)
    buildHeaderLine(surface, "CHRONO_LINE", x, y, 200, HEADER_RIGHT_END)
    y = y + 70
    shapes["CHRONO_DATE"] = ls.Bar(surface, x, y, 400, 40, ls.Colours.BACKGROUND, "", ls.Alignment.LEFT, fonts.TextSize.LARGE)
    shapes["CHRONO_DATE"].textColour = sidebarColour1

    y = y + 45

    # The boxes are as wide as the digits are in the current font, so they fit
    # whatever the font is. The hour is lined up on the right of its box and the
    # minute on the left of its, so both stay next to the colon.
    font = fonts.fontFor(fonts.TextSize.XXL)
    digitsWidth = max(font.size(digit * 2)[0] for digit in "0123456789") + 2 * ls.BAR_TEXT_PAD
    colonWidth = font.size(":")[0] + 2 * ls.BAR_TEXT_PAD

    # The hour, colon and minute boxes sit edge to edge without overlapping.
    # Each Bar clears its own box before drawing, so if they overlapped, the
    # flashing colon would wipe part of a digit whenever that digit wasn't
    # also redrawn in the same frame.
    shapes["CHRONO_HOUR"] = ls.Bar(surface, x, y, digitsWidth, 130, ls.Colours.BACKGROUND, "", ls.Alignment.RIGHT, fonts.TextSize.XXL)
    x = x + digitsWidth
    shapes["CHRONO_COLON1"] = ls.Bar(surface, x, y, colonWidth, 130, ls.Colours.BACKGROUND, ":", ls.Alignment.CENTRE, fonts.TextSize.XXL)
    x = x + colonWidth
    shapes["CHRONO_MIN"] = ls.Bar(surface, x, y, digitsWidth, 130, ls.Colours.BACKGROUND, "", ls.Alignment.LEFT, fonts.TextSize.XXL)
    x = x + digitsWidth + 5
    shapes["CHRONO_TIMEZONE"] = ls.Bar(surface, x, y, 100, 50, ls.Colours.BACKGROUND, "", ls.Alignment.LEFT, fonts.TextSize.MEDIUM)
    shapes["CHRONO_SEC"] = ls.Bar(surface, x, y + 50, 100, 80, ls.Colours.BACKGROUND, "", ls.Alignment.LEFT, fonts.TextSize.XL)

    # A row of 60 segments under the time that lights up one a second
    shapes["CHRONO_SECONDS"] = ls.Meter(surface, left, y + 138, x + 100 - left, 10, sidebarColour1, 60, 2, 0, ls.Direction.HORIZONTAL)



# Weather Now
def buildShortRangeScan(surface, x, y):
    
    # Coordinates of top left corner. Everything is relative to this
    shapes["SHORT_RANGE_SCAN"] = ls.Pill(surface, x, y, 300, 40, borderColour1, "DIGITAL SEAWEED", ls.Alignment.CENTRE, fonts.TextSize.MEDIUM)
    buildHeaderLine(surface, "SHORT_RANGE_LINE", x, y, 300, HEADER_LEFT_END)
    y1 = y + 54
    
    shapes["SRS_TEMP"] = ls.Bar(surface, x, y1, 500, 70, ls.Colours.BACKGROUND, "", ls.Alignment.LEFT, fonts.TextSize.XL)    
    y1 += 72    

    shapes["SRS_WEATHER"] = ls.Bar(surface, x, y1, 500, 40, ls.Colours.BACKGROUND, "", ls.Alignment.LEFT, fonts.TextSize.LARGE)    
    shapes["SRS_WEATHER"].textColour = sidebarColour1
    y1 += 50

    shapes["SRS_FEELSLIKE"] = ls.Bar(surface, x, y1, 500, 26, ls.Colours.BACKGROUND, "", ls.Alignment.LEFT, fonts.TextSize.MEDIUM)    
    
    y1 += 30
    shapes["SRS_RH"] = ls.Bar(surface, x, y1, 500, 26, ls.Colours.BACKGROUND, "", ls.Alignment.LEFT, fonts.TextSize.MEDIUM)    
    
    y1 += 30
    shapes["SRS_WIND"] = ls.Bar(surface, x, y1, 500, 26, ls.Colours.BACKGROUND, "", ls.Alignment.LEFT, fonts.TextSize.MEDIUM)    
    
    y1 += 30
    shapes["SRS_PRECIP"] = ls.Bar(surface, x, y1, 500, 26, ls.Colours.BACKGROUND, "", ls.Alignment.LEFT, fonts.TextSize.MEDIUM)    

    shapes["SRS_IMAGE"] = ls.Image(surface, x+550, y+100, None)



  
# Weather Icons For the next day
def buildForecast(surface, x, y):  
    FORECAST_W = 65
    FORECAST_H = 148
    TIME_H = 28
    TEMP_H = 26
    RAIN_H = 26
    
    
    x2 = x + FORECAST_COUNT * FORECAST_W
    pygame.draw.line(surface, borderColour2, (x,y), (x2,y))

    y2 = y + TIME_H + 1
    pygame.draw.line(surface, borderColour2, (x,y2), (x2,y2))

    y2 = y + FORECAST_H    
    pygame.draw.line(surface, borderColour2, (x,y2), (x2,y2))

    for i in range(0,FORECAST_COUNT+1):
        x2 = x + i*FORECAST_W
        pygame.draw.line(surface, borderColour2, (x2,y), (x2,y2))
    
    for i in range(0,FORECAST_COUNT):
        x2 = x + i*FORECAST_W + 1
        
        b = ls.Bar(surface, x2, y+1, FORECAST_W - 1, TIME_H, sidebarColour1, "--:--", 
                   ls.Alignment.CENTRE, fonts.TextSize.MEDIUM)
        shapes["FORECAST_" + str(i) + "_TIME"] = b
    
        shapes["FORECAST_" + str(i) + "_ICON"] = ls.Image(surface, x2 + (FORECAST_W - 1 - ICON_SIZE_SMALL) // 2, y+TIME_H+4)
    
        b = ls.Bar(surface, x2, y+FORECAST_H-TEMP_H-RAIN_H-1, FORECAST_W - 1, TEMP_H, 
            ls.Colours.BACKGROUND, None, ls.Alignment.CENTRE, fonts.TextSize.MEDIUM)
        b.textColour = sidebarColour1
        shapes["FORECAST_" + str(i) + "_TEMP"] = b

        # The rain expected in that hour, in mm
        b = ls.Bar(surface, x2, y+FORECAST_H-RAIN_H-1, FORECAST_W - 1, RAIN_H, 
            ls.Colours.BACKGROUND, None, ls.Alignment.CENTRE, fonts.TextSize.LIST)
        b.textColour = sidebarColour2
        shapes["FORECAST_" + str(i) + "_RAIN"] = b
    
  
  
# Weather forecast for the next few days
def buildLongRangeScan(surface, x, y):
    
    # Coordinates of top left corner. Everything is relative to this
    shapes["LONG_RANGE_SCAN"] = ls.Pill(surface, x, y, 300, 40, borderColour1, "CRYSTAL BALL", ls.Alignment.CENTRE, fonts.TextSize.MEDIUM)
    buildHeaderLine(surface, "LONG_RANGE_LINE", x, y, 300, HEADER_LEFT_END)
    y += 50

    x1 = x
    shapes["LRS_TITLE_1"] = ls.Label(surface, x1+10, y, "DAY", 
                                sidebarColour2, ls.Alignment.LEFT, fonts.TextSize.SMALL)        
    x2 = x1 + 80
    shapes["LRS_TITLE_2"] = ls.Label(surface, x2+10, y, "CONDITION", 
                                sidebarColour2, ls.Alignment.LEFT, fonts.TextSize.SMALL)        
    x3 = x2 + 300    
    shapes["LRS_TITLE_3"] = ls.Label(surface, x3, y, "TEMP MAX", 
                                sidebarColour2, ls.Alignment.LEFT, fonts.TextSize.SMALL)   
    x4 = x3 + 90    
    shapes["LRS_TITLE_4"] = ls.Label(surface, x4, y, "TEMP MIN", 
                                sidebarColour2, ls.Alignment.LEFT, fonts.TextSize.SMALL)   
    x5 = x4 + 120    
    shapes["LRS_TITLE_5"] = ls.Label(surface, x5+30, y, "RAIN", 
                                sidebarColour2, ls.Alignment.LEFT, fonts.TextSize.SMALL)   
    x6 = x5 + 100    
    shapes["LRS_TITLE_6"] = ls.Label(surface, x6, y, "PROBABILITY", 
                                sidebarColour2, ls.Alignment.LEFT, fonts.TextSize.SMALL)    

    y += 40
    for i in range(lw.FORECAST_DAYS):
      
        shapes["LRS_" + str(i) + "_DAY"] = ls.Bar(surface, x1, y, 75, 30, ls.Colours.BACKGROUND, "", ls.Alignment.LEFT, fonts.TextSize.MEDIUM)        
        shapes["LRS_" + str(i) + "_COND"] = ls.Bar(surface, x2, y, 295, 30, ls.Colours.BACKGROUND, "", ls.Alignment.LEFT, fonts.TextSize.MEDIUM)
        shapes["LRS_" + str(i) + "_MAX"] = ls.Bar(surface, x3, y, 85, 30, ls.Colours.BACKGROUND, "", ls.Alignment.CENTRE, fonts.TextSize.MEDIUM)
        shapes["LRS_" + str(i) + "_MIN"] = ls.Bar(surface, x4, y, 85, 30, ls.Colours.BACKGROUND, "", ls.Alignment.CENTRE, fonts.TextSize.MEDIUM)
        shapes["LRS_" + str(i) + "_RAIN"] = ls.Bar(surface, x5, y, 95, 30, ls.Colours.BACKGROUND, "", ls.Alignment.RIGHT, fonts.TextSize.MEDIUM)
        shapes["LRS_" + str(i) + "_PROB"] = ls.Bar(surface, x6, y, 90, 30, ls.Colours.BACKGROUND, "", ls.Alignment.RIGHT, fonts.TextSize.MEDIUM)

        shapes["LRS_" + str(i) + "_DAY"].textColour = sidebarColour1        
        shapes["LRS_" + str(i) + "_COND"].textColour = sidebarColour1        
        shapes["LRS_" + str(i) + "_MAX"].textColour = sidebarColour1        
        shapes["LRS_" + str(i) + "_MIN"].textColour = sidebarColour1        
        shapes["LRS_" + str(i) + "_RAIN"].textColour = sidebarColour1        
        shapes["LRS_" + str(i) + "_PROB"].textColour = sidebarColour1        

        y = y + 30


def buildGraphs(surface, x, y):    
    step = GRAPH_WIDTH + GRAPH_GAP
    shapes["GRAPH_TEMP"] = ls.Graph(surface, x, y, GRAPH_WIDTH, 200, sidebarColour1, f"TEMP {DEG}C", None, None, "{:.0f}")
    shapes["GRAPH_RAIN"] = ls.Graph(surface, x + step, y, GRAPH_WIDTH, 200, sidebarColour1, "MM RAIN", None, None, "{:.1f}", ls.GraphStyle.BAR)
    shapes["GRAPH_PRES"] = ls.Graph(surface, x + 2 * step, y, GRAPH_WIDTH, 200, sidebarColour1, "MBAR", None, None, "{:.0f}")
    



# Calendar events
def buildCaptainsLog(surface, x, y, width):
    global logEventTextWidth

    # Coordinates of top left corner. Everything is relative to this. The log is width
    # pixels wide, and its title's line runs on to the end of that.
    shapes["CAPTAINS_LOG"] = ls.Pill(surface, x, y, 300, 40, borderColour1, "CAPTAIN'S LOG", ls.Alignment.CENTRE, fonts.TextSize.MEDIUM)
    buildHeaderLine(surface, "CAPTAINS_LOG_LINE", x, y, 300, x + width)
    y1 = y + 70
    
    # Size the date and time columns to fit their widest text in the current
    # font, plus the gap, so the spacing stays the same whatever the font is.
    font = fonts.fontFor(fonts.TextSize.MEDIUM)
    dateWidth = max(font.size(text)[0] for text in ("TOMORROW", "WED 28 MAR", "MON 28 NOV")) + CALENDAR_COLUMN_GAP
    timeWidth = font.size("00:00")[0] + CALENDAR_COLUMN_GAP

    # The event column takes the rest of the width. A longer event is cut short (see
    # updateCaptainsLog), as text that sticks out of its Bar is never cleared.
    eventWidth = width - dateWidth - timeWidth
    logEventTextWidth = eventWidth - 2 * ls.BAR_TEXT_PAD

    for i in range(CALENDAR_EVENT_COUNT):
        col = sidebarColour2 if i%2 else sidebarColour1
        
        # Date and time columns, side by side in the space before the event
        shapes[f"SRS_{i}_DATE"] = \
            ls.Bar(surface, x, y1, dateWidth, 26, ls.Colours.BACKGROUND, "", ls.Alignment.LEFT, fonts.TextSize.MEDIUM)
        shapes[f"SRS_{i}_DATE"].textColour = col

        shapes[f"SRS_{i}_TIME"] = \
            ls.Bar(surface, x+dateWidth, y1, timeWidth, 26, ls.Colours.BACKGROUND, "", ls.Alignment.LEFT, fonts.TextSize.MEDIUM)
        shapes[f"SRS_{i}_TIME"].textColour = col

        shapes[f"SRS_{i}_EVENT"] = \
            ls.Bar(surface, x+dateWidth+timeWidth, y1, eventWidth, 26, ls.Colours.BACKGROUND, "", ls.Alignment.LEFT, fonts.TextSize.MEDIUM)    
        shapes[f"SRS_{i}_EVENT"].textColour = col
            
        y1 += 31    

    
# Radar showing the aircraft near the receiver
def buildRadar(surface, x, y):

    shapes["SCANNERS"] = ls.Pill(surface, x, y, 200, 40, borderColour1, "SCANNERS", ls.Alignment.CENTRE, fonts.TextSize.MEDIUM)

    buildHeaderLine(surface, "SCANNERS_LINE", x, y, 200, HEADER_RIGHT_END)    

    # Coordinates of top left corner of the radar. The list of aircraft goes to the
    # right of it, from the top of its circle to the border of the screen.
    # The airport is marked where it is from the receiver: its distance and bearing
    distance, bearing = ac.distance_and_bearing(ac.HOME_LAT, ac.HOME_LON, AIRPORT_LAT, AIRPORT_LON)
    airport = [(bearing, distance, AIRPORT_NAME)]

    runways = []
    for (lat1, lon1), (lat2, lon2) in AIRPORT_RUNWAYS:
        distance1, bearing1 = ac.distance_and_bearing(ac.HOME_LAT, ac.HOME_LON, lat1, lon1)
        distance2, bearing2 = ac.distance_and_bearing(ac.HOME_LAT, ac.HOME_LON, lat2, lon2)
        runways.append((bearing1, distance1, bearing2, distance2))

    shapes["RADAR"] = ls.Radar(surface, x, y+100, RADAR_SIZE, sidebarColour2, ac.RADIUS_NM, RADAR_RING_NM, "NM",
                               markers=airport, lines=runways)

    buildAircraftList(surface, x + RADAR_SIZE + 10, y + 100 + ls.RADAR_MARGIN - 8 - CONTACT_LIST_RAISE)


# Details of the aircraft in the list, three lines each
def buildAircraftList(surface, x, y):
    right = scr.SCREEN_WIDTH - BORDER
    indent = contactColumnWidth(CONTACT_LINE_1[0][0])

    for i in range(CONTACT_COUNT):
        blockY = y + i * (len(CONTACT_LINES) * CONTACT_LINE_HEIGHT + CONTACT_BLOCK_GAP)

        for line, columns in enumerate(CONTACT_LINES, start=1):
            colour = ls.Colours.WHITE if line==1 else sidebarColour1
            lineX = x if line == 1 else x + indent
            buildContactLine(surface, lineX, blockY + (line - 1) * CONTACT_LINE_HEIGHT, right, i, line, columns, colour)

        # The icon for the kind and size of the aircraft, in the space under its number
        shapes[f"CONTACT_{i}_ICON"] = ls.AircraftIcon(surface, x, blockY + CONTACT_LINE_HEIGHT, indent,
                                                      2 * CONTACT_LINE_HEIGHT - 1, sidebarColour1)

        # A line in the middle of the gap under it, to separate it from the next. It is the
        # colour of the background (so not seen) until there is an aircraft below it.
        if i < CONTACT_COUNT - 1:
            ruleY = blockY + len(CONTACT_LINES) * CONTACT_LINE_HEIGHT + (CONTACT_BLOCK_GAP - CONTACT_RULE_HEIGHT) // 2
            shapes[f"CONTACT_{i}_RULE"] = ls.Bar(surface, x, ruleY, right - x, CONTACT_RULE_HEIGHT, ls.Colours.BACKGROUND,
                                                 "", ls.Alignment.LEFT, CONTACT_TEXT_SIZE)

    # Shown over the whole list when it is empty. It is made after the list so that it is
    # redrawn after it, as every shape is redrawn in the order it was made.
    #listHeight = CONTACT_COUNT * (len(CONTACT_LINES) * CONTACT_LINE_HEIGHT + #CONTACT_BLOCK_GAP) - CONTACT_BLOCK_GAP
    listHeight = 300
    shapes["CONTACT_SEARCH"] = ls.Searching(surface, x, y, right - x, listHeight,       sidebarColour1, sidebarColour2, SEARCH_TITLE_NO_CONTACTS)


# How wide a column of that list is: its widest text in the current font (in capitals,
# which is how it is drawn), plus the gap, so the spacing stays the same whatever the font is.
def contactColumnWidth(widest, gap=CONTACT_COLUMN_GAP):
    return fonts.fontFor(CONTACT_TEXT_SIZE).size(widest.upper())[0] + gap


# One line of one aircraft: a Bar for each column, side by side from x. A column
# with no widest text (None) takes all the width that is left, up to right.
# The most text each Bar can hold is kept in contactTextWidth: a longer text would
# stick out of the Bar, and what sticks out is never cleared when the text changes.
def buildContactLine(surface, x, y, right, i, line, columns, colour):
    for column, (widest, alignment) in enumerate(columns):
        gap = CONTACT_LINE_1_GAP if line == 1 and column > 0 else CONTACT_COLUMN_GAP

        if widest is None:
            width = right - x
        else:
            width = contactColumnWidth(widest, gap)

        bar = ls.Bar(surface, x, y, width, CONTACT_LINE_HEIGHT, ls.Colours.BACKGROUND, "", alignment, CONTACT_TEXT_SIZE)
        bar.textColour = colour
        shapes[f"CONTACT_{i}_{line}_{column}"] = bar
        contactTextWidth[f"CONTACT_{i}_{line}_{column}"] = width - 2 * ls.BAR_TEXT_PAD

        x += width


# The text, cut short if need be so that it fits in maxWidth pixels in that text size's font
# (which draws it in capitals). The size is the aircraft list's unless another is given.
def fitText(text, maxWidth, textSize=CONTACT_TEXT_SIZE):
    if text is None:
        return None

    font = fonts.fontFor(textSize)

    while text and font.size(text.upper())[0] > maxWidth:
        text = text[:-1]

    return text.rstrip()


# The text with whole words taken off the end until it fits in maxWidth pixels, so that a long
# airline like 'Turkish Airlines' comes out as 'Turkish' and not as 'Turkish Airlin'. A single
# word that is still too long is left for fitText to cut short.
def shortenWords(text, maxWidth, textSize=CONTACT_TEXT_SIZE):
    if text is None:
        return None

    font = fonts.fontFor(textSize)

    while " " in text and font.size(text.upper())[0] > maxWidth:
        text = text.rsplit(" ", 1)[0]

    return text


# The model of an aircraft for the list, or None. When there isn't room for it all, the maker is
# dropped from the front ('Embraer ERJ 190' becomes 'ERJ 190'), then words from the end.
def modelText(aircraftType, maxWidth, textSize=CONTACT_TEXT_SIZE):
    if aircraftType is None or not aircraftType.model:
        return None

    model = aircraftType.model
    maker = aircraftType.manufacturer

    tooWide = fonts.fontFor(textSize).size(model.upper())[0] > maxWidth
    if tooWide and maker and model.upper().startswith(maker.upper() + " "):
        model = model[len(maker) + 1:]

    return shortenWords(model, maxWidth, textSize)


def num(value, fmt="{:.1f}"):
    
    """Format a weather value, or '--' if it's missing."""
    return "--" if value is None else fmt.format(value)



def updateShortRangeScan(weather):

    current = weather.current
    hourly = weather.hourly

    # Nothing has been fetched yet
    if (current.time is None) or (not hourly):
        return

    nextHour = next_hour_index(hourly, time.time())

    # Wind, e.g. "WIND : 18 KTS NW (Force 5 Fresh breeze)". The direction and
    # force are left off if there's no data for them.
    windText = f"WIND : {num(current.wind_speed, '{:.0f}')} KTS"

    degrees, compass = current.wind_direction
    if compass:
        windText += " " + compass

    force, forceName = current.wind_beaufort
    if force is not None:
        windText += f" (Force {force} {forceName})"

    shapes["SRS_TEMP"].text      = f"{num(current.temperature)}{DEG}C"
    if current.weather_code is None:
        shapes["SRS_WEATHER"].text = current.weather_description
    else:
        shapes["SRS_WEATHER"].text = f"{current.weather_code} : {current.weather_description}"
    shapes["SRS_FEELSLIKE"].text = f"FEELS LIKE : {num(current.apparent_temperature, '{:.0f}')} {DEG}C"
    shapes["SRS_RH"].text        = f"HUMIDITY : {num(current.humidity, '{:.0f}')} %"
    shapes["SRS_WIND"].text      = windText
    shapes["SRS_PRECIP"].text    = f"RAIN IN CURRENT HOUR : {num(hourly[nextHour].precipitation)} mm"

    shapes["SRS_IMAGE"].image = getWeatherIcon(ICON_SIZE_LARGE, current.weather_code)



def updateForecast(weather):
    hourly = weather.hourly

    if not hourly:
        return

    # Map each hourly UTC timestamp to its HourlyWeather
    hourByTime = {}
    for hour in hourly:
        hourByTime[hour.time] = hour

    # Start of the current hour, as real (UTC) unix time
    t = (int(time.time()) // 3600) * 3600

    for i in range(FORECAST_COUNT):
        # Convert to local time only here, for display
        shapes[f"FORECAST_{i}_TIME"].text = time.strftime("%H:%M", time.localtime(t))

        hour = hourByTime.get(t)
        if hour is None:
            shapes[f"FORECAST_{i}_TEMP"].text = "--"
            shapes[f"FORECAST_{i}_RAIN"].text = "--"
            shapes[f"FORECAST_{i}_ICON"].image = None
        else:
            shapes[f"FORECAST_{i}_TEMP"].text = f"{num(hour.temperature, '{:.0f}')}{DEG}"
            shapes[f"FORECAST_{i}_RAIN"].text = f"{num(hour.precipitation)}mm"
            shapes[f"FORECAST_{i}_ICON"].image = getWeatherIcon(ICON_SIZE_SMALL, hour.weather_code)

        t += FORECAST_STEP_HOURS * 3600




def updateLongRangeScan(weather):

    daily = weather.daily

    if (not daily):
        return

    # Only as many rows as were built, even if the API sends more days.
    # A day the API didn't send shows as blanks.
    for i in range(lw.FORECAST_DAYS):
        if i < len(daily):
            day = daily[i]
        else:
            day = wd.DailyWeather()

        row = "LRS_" + str(i)
        shapes[row + "_DAY"].text = unix_to_weekday(day.time)
        shapes[row + "_COND"].text = day.weather_description
        shapes[row + "_MAX"].text = f"{num(day.temperature_max, '{:.0f}')}{DEG}"
        shapes[row + "_MIN"].text = f"{num(day.temperature_min, '{:.0f}')}{DEG}"
        shapes[row + "_RAIN"].text = f"{num(day.precipitation)} mm"
        shapes[row + "_PROB"].text = f"{num(day.precipitation_probability, '{:.0f}')} %"


# Change a shape's colour, but only if it's different, so the shape isn't
# redrawn for no reason.
def setColour(shape, colour):
    if shape.colour != colour:
        shape.colour = colour



def updateCaptainsLog(fetcher, currentUnixTime):
    events = fetcher.get_calendar().events
    error = fetcher.get_error()

    # (The fetcher prints each failure, with its traceback, when it happens.)

    # The title goes red while the latest fetch has failed. The events below
    # are then the last good ones, or none if there has never been a good fetch.
    if error:
        setColour(shapes["CAPTAINS_LOG"], ls.Colours.RED)
    else:
        setColour(shapes["CAPTAINS_LOG"], borderColour1)

    # Fill the rows, and blank any that have no event (so old events are cleared)
    for i in range(CALENDAR_EVENT_COUNT):
        if i < len(events):
            event = events[i]
            shapes[f"SRS_{i}_DATE"].text = event.date_text(currentUnixTime)
            shapes[f"SRS_{i}_TIME"].text = event.time_text
            shapes[f"SRS_{i}_EVENT"].text = fitText(event.summary, logEventTextWidth, fonts.TextSize.MEDIUM)
        else:
            shapes[f"SRS_{i}_DATE"].text = None
            shapes[f"SRS_{i}_TIME"].text = None
            shapes[f"SRS_{i}_EVENT"].text = None



# How big to draw an aircraft on the radar: the higher it is, the smaller.
# The square root makes the sizes differ more at low altitude, where most of the
# aircraft are, than a straight line would. An unknown altitude is drawn halfway, and an
# aircraft above RADAR_PASSING_FT is drawn smaller than any of the others.
def radarIconSize(altitude_ft):
    if altitude_ft is not None and altitude_ft > RADAR_PASSING_FT:
        return RADAR_ICON_PASSING

    if altitude_ft is None:
        fraction = 0.5
    else:
        fraction = math.sqrt(min(max(altitude_ft, 0), RADAR_ALTITUDE_MAX_FT) / RADAR_ALTITUDE_MAX_FT)

    return RADAR_ICON_BIG - fraction * (RADAR_ICON_BIG - RADAR_ICON_SMALL)



# Where an aircraft is thought to be now: where it was reported, moved on in the
# direction it is flying for the `seconds` since, at its speed. This is what makes the
# icons glide between reports, which only come every few seconds. Returns
# (bearing, distance) from the receiver. An aircraft that hasn't reported its speed
# or direction stays where it was reported.
def projectedPosition(plane, seconds):
    if plane.speed_kt is None or plane.track_deg is None:
        return plane.bearing_deg, plane.distance_nm

    miles = plane.speed_kt * seconds / 3600
    track = math.radians(plane.track_deg)

    # A degree of latitude is 60 nautical miles, and a degree of longitude is less than that
    # by the cosine of the latitude
    latitude = plane.latitude + miles * math.cos(track) / 60
    longitude = plane.longitude + miles * math.sin(track) / (60 * math.cos(math.radians(plane.latitude)))

    distance, bearing = ac.distance_and_bearing(ac.HOME_LAT, ac.HOME_LON, latitude, longitude)
    return bearing, distance



# How different two colours are: bigger is more different
def colourDistance(colour1, colour2):
    return sum((a - b) ** 2 for a, b in zip(colour1, colour2))



# Whichever of the colours is the most different from this one
def furthestColour(colours, colour):
    furthest = colours[0]

    for candidate in colours:
        if colourDistance(candidate, colour) > colourDistance(furthest, colour):
            furthest = candidate

    return furthest



# The colour of an aircraft on the radar (and of its altitude in the list): SERVICE_COLOUR if it
# belongs to an emergency service, otherwise one colour if it is climbing, another if it is
# descending, otherwise the sidebar colour.
def radarColour(plane):
    if plane.service:
        return SERVICE_COLOUR

    rate = plane.vertical_rate_fpm

    if rate is not None and rate >= RADAR_VERTICAL_FPM:
        return furthestColour(RADAR_CLIMB_COLOURS, sidebarColour1)

    if rate is not None and rate <= -RADAR_VERTICAL_FPM:
        return furthestColour(RADAR_DESCEND_COLOURS, sidebarColour1)

    return sidebarColour1



# What is drawn round an aircraft to mark it (see ls.drawMarker), or None: a ring that flashes
# red and white if it is squawking an emergency, a diamond if it belongs to an emergency
# service, or brackets if it is military
def planeMarker(plane, now):
    if plane.emergency:
        return ("circle", ls.Colours.RED if blinkIsOn(now) else ls.Colours.WHITE)

    if plane.service:
        return ("diamond", SERVICE_MARKER_COLOUR)

    if plane.military:
        return ("brackets", MILITARY_MARKER_COLOUR)

    return None



# True if the aircraft came into range (see contactEvents) within the last FLASH_SECONDS
def isNewContact(firstSeen, icao, now):
    name, seen = firstSeen.get(icao, (None, 0))

    return seen > 0 and now - seen < FLASH_SECONDS



# True for half of each blink
def blinkIsOn(now):
    return int(now * FLASH_BLINKS_PER_SECOND * 2) % 2 == 0



# Update the radar. This is done every frame, because the aircraft are moved on a little
# each time, and the radar itself is animated. firstSeen is the dictionary kept by
# contactEvents. Returns the aircraft, in the order of the list (see listOrder).
def updateRadar(fetcher, firstSeen, now):
    data = fetcher.get_aircraft()
    planes = emergenciesFirst(data.aircraft)

    # The radar goes red while the latest fetch has failed. The aircraft are
    # then the last good ones, or none if there has never been a good fetch.
    if fetcher.get_error():
        setColour(shapes["RADAR"], ls.Colours.RED)
    else:
        setColour(shapes["RADAR"], sidebarColour2)

    # How long ago the aircraft were reported
    seconds = 0
    if data.last_success is not None:
        seconds = min(max(now - data.last_success, 0), RADAR_PROJECT_SECONDS)

    # One blip per aircraft: where it is, which way it is heading, how big to
    # draw it, its colour, and its number if it is in the list (1 = first).
    blips = []
    for i, plane in enumerate(planes):
        number = str(i + 1) if i < CONTACT_COUNT else None
        bearing, distance = projectedPosition(plane, seconds)

        colour = radarColour(plane)
        if isNewContact(firstSeen, plane.icao, now) and blinkIsOn(now):
            colour = ls.Colours.WHITE

        blips.append((bearing, distance, plane.track_deg,
                      radarIconSize(plane.altitude_ft), colour, number, plane.trail,
                      plane.kind, planeMarker(plane, now)))

    shapes["RADAR"].blips = blips

    return planes



# Contacts coming into range and going out of it. known is a dictionary, kept between
# calls and changed here, of the aircraft in range: icao -> (name, time it came in). The
# time is 0 for the ones that were already there on the first call (firstPoll), which
# aren't new. Returns the messages to announce, e.g. 'CONTACT DETECTED BAW123'.
def contactEvents(known, planes, now, firstPoll):
    present = {plane.icao: plane for plane in planes}
    arrived = []
    left = []

    for icao, plane in present.items():
        if icao not in known:
            name = plane.callsign or icao
            known[icao] = (name, 0 if firstPoll else now)

            if not firstPoll:
                arrived.append(name)

    for icao in list(known):
        if icao not in present:
            left.append(known[icao][0])
            del known[icao]

    return eventMessages("DETECTED", arrived) + eventMessages("LOST", left)



# The messages for these contacts, e.g. 'CONTACT LOST BAW123', one each, or a single
# message with a number if there are more than EVENT_MAX_NAMES of them
def eventMessages(verb, names):
    if len(names) > EVENT_MAX_NAMES:
        return [f"{len(names)} CONTACTS {verb}"]

    return [f"CONTACT {verb} {name}" for name in names]



# The colours of the text in the list, which are set every frame as a new contact makes its
# row blink: the first line white and the other two in the sidebar colour, the altitude in the
# colour of its aircraft on the radar, and white for the blinks.
def colourAircraftList(planes, firstSeen, now):
    for i in range(CONTACT_COUNT):
        plane = planes[i] if i < len(planes) else None
        flashing = plane is not None and isNewContact(firstSeen, plane.icao, now) and blinkIsOn(now)

        for line, columns in enumerate(CONTACT_LINES, start=1):
            for column in range(len(columns)):
                colour = ls.Colours.WHITE if line == 1 else sidebarColour1

                if plane is not None and line == 2 and column == 0:
                    colour = radarColour(plane)

                if flashing:
                    colour = ls.Colours.WHITE

                # The squawk flashes red and white if it is an emergency
                if plane is not None and plane.emergency and line == 2 and column == 4:
                    colour = ls.Colours.RED if blinkIsOn(now) else ls.Colours.WHITE

                setTextColour(shapes[f"CONTACT_{i}_{line}_{column}"], colour)

        # The icon is in the colour of the aircraft on the radar, with the same marker
        if plane is not None:
            setColour(shapes[f"CONTACT_{i}_ICON"], radarColour(plane))
            shapes[f"CONTACT_{i}_ICON"].marker = planeMarker(plane, now)



# For sorting: False for an aircraft squawking an emergency, so that it comes first
def isNotEmergency(plane):
    return not plane.emergency



# For sorting the list: any aircraft squawking an emergency first, then the ones that are lowest and
# nearest. Each thousand feet of height counts as LIST_NM_PER_1000_FT nautical miles of distance, so
# an aircraft that is low and a bit further away comes before a near one that is high. One whose height
# isn't known comes last.
def listOrder(plane):
    altitude = plane.altitude_ft if plane.altitude_ft is not None else math.inf

    return isNotEmergency(plane), plane.distance_nm + altitude / 1000 * LIST_NM_PER_1000_FT, plane.distance_nm



# The aircraft in the order of the list, so that an emergency is always in it and has a number on the radar
def emergenciesFirst(planes):
    return sorted(planes, key=listOrder)



# The name an aircraft is announced by: its callsign, or its hex address if it has none
def contactName(plane):
    return plane.callsign or plane.icao



# The aircraft that have just started squawking an emergency code, the military ones that have just
# come into range, and the emergency services' ones that have just come within ac.SERVICE_RADIUS_NM. raised is a dictionary kept between calls
# and changed here: icao -> the alerts that aircraft has already raised (its squawk, "MIL" or "SVC"), so each is raised once
# however long it goes on. One that leaves range is forgotten, and raises them again if it returns.
def newAlerts(raised, planes):
    present = {plane.icao for plane in planes}

    for icao in list(raised):
        if icao not in present:
            del raised[icao]

    emergencies = []
    military = []
    services = []

    for plane in planes:
        done = raised.setdefault(plane.icao, set())

        if plane.emergency and plane.squawk not in done:
            done.add(plane.squawk)
            emergencies.append(plane)

        if plane.military and "MIL" not in done:
            done.add("MIL")
            military.append(plane)

        if plane.service and plane.distance_nm <= ac.SERVICE_RADIUS_NM and "SVC" not in done:
            done.add("SVC")
            services.append(plane)

    return emergencies, military, services



# What the emergency popup says: its title, and its three lines of text
def emergencyPopupText(plane):
    details = f"{num(plane.altitude_ft, '{:,.0f}')} ft    {num(plane.speed_kt, '{:.0f}')} kt    " \
              f"{num(plane.distance_nm)} NM    {num(plane.bearing_deg)}{DEG}"

    return f"EMERGENCY SQUAWK {plane.squawk}", (contactName(plane), plane.emergency, details)



# Announce the new alerts: a message in the status line for each, the popup and its alarm for an
# emergency, and a beep for a military aircraft (an emergency services aircraft just gets its message).
# state is a dictionary that holds when the alarm is next due (see repeatEmergencyAlarm), and is
# changed here.
def raiseAlerts(emergencies, military, services, popup, state):
    for plane in services:
        shapes["LCARS_STATUS"].message(f"EMERGENCY SERVICES CONTACT {contactName(plane)} {plane.service}")

    for plane in military:
        shapes["LCARS_STATUS"].message(f"MILITARY CONTACT {contactName(plane)}")

    if military:
        sound.play("MILITARY")

    for plane in emergencies:
        shapes["LCARS_STATUS"].message(f"EMERGENCY SQUAWK {plane.squawk} {contactName(plane)}")

    # Only one popup, for the latest. Its alarm sounds at once.
    if emergencies:
        title, lines = emergencyPopupText(emergencies[-1])
        popup.show(title, lines, POPUP_SECONDS)
        state["nextAlarm"] = 0



# While the emergency popup is up, sound its alarm again every POPUP_BEEP_SECONDS
def repeatEmergencyAlarm(popup, state, now):
    if popup.visible and now >= state["nextAlarm"]:
        sound.play("EMERGENCY")
        state["nextAlarm"] = now + POPUP_BEEP_SECONDS



# Show the scanning animation in place of the list when there are no aircraft. If the last
# fetch failed, it says so, as then it is not that there are none in range.
def updateSearching(planes, error):
    search = shapes["CONTACT_SEARCH"]
    search.title = SEARCH_TITLE_NO_SIGNAL if error else SEARCH_TITLE_NO_CONTACTS
    search.active = len(planes) == 0



# Change a shape's text colour, but only if it's different, so the shape isn't
# redrawn for no reason.
def setTextColour(shape, colour):
    if shape.textColour != colour:
        shape.textColour = colour



# The direction an aircraft is heading as three digits and a degree sign ("051°"), or
# "--" if it isn't known. It is rounded to a whole degree, and 360 is shown as 000.
def headingText(track):
    if track is None:
        return "--"

    return f"{round(track) % 360:03d}{DEG}"



# Where an aircraft is flying from and to, as the names of the two places
# ("Prague"), or their codes if there are no names. "--" is shown for one that
# isn't known: no callsign, no route found, or not looked up yet.
def routePlaces(route):
    if route is None:
        return "--", "--"

    return route.origin_name or route.origin or "--", route.destination_name or route.destination or "--"



# Fill the list with the first aircraft (they are already in the order of the list,
# see listOrder), and blank any rows that have no aircraft.
def updateAircraftList(planes, routeFetcher, modelFetcher):
    for i in range(CONTACT_COUNT):
        # The line between this aircraft and the next is only there if there is a next one
        if i < CONTACT_COUNT - 1:
            shapes[f"CONTACT_{i}_RULE"].colour = CONTACT_RULE_COLOUR if i + 1 < len(planes) else ls.Colours.BACKGROUND

        if i < len(planes):
            plane = planes[i]

            # Looked up in the background, so nothing is known at first
            route = routeFetcher.get(plane.callsign) if plane.callsign else None
            route = lk.route_at_airport(route, lk.HOME_AIRPORT)    # only flights to or from our airport
            aircraftType = modelFetcher.get(plane.icao) if plane.icao else None
            airlineWidth = contactTextWidth[f"CONTACT_{i}_1_{len(CONTACT_LINE_1) - 2}"]
            modelWidth = contactTextWidth[f"CONTACT_{i}_1_{len(CONTACT_LINE_1) - 1}"]
            origin, destination = routePlaces(route)

            # A military or emergency services aircraft has no airline, so it says what it is instead
            airline = route.airline if route else None
            if plane.service and not airline:
                airline = plane.service
            elif plane.military and not airline:
                airline = "MILITARY"

            line1 = (str(i + 1),
                     plane.callsign or plane.icao,
                     aircraftType.registration if aircraftType else None,
                     shortenWords(airline, airlineWidth),
                     modelText(aircraftType, modelWidth))
            line2 = (num(plane.altitude_ft, "{:,.0f}") + " ft",
                     num(plane.speed_kt, "{:.0f}") + " kt",
                     headingText(plane.track_deg),
                     num(plane.distance_nm) + " NM",
                     plane.squawk or "--")
            line3 = (f"{origin} > {destination}" if route else None,)    # the route is last, blank if there is none
            shapes[f"CONTACT_{i}_ICON"].kind = plane.kind
            shapes[f"CONTACT_{i}_ICON"].visible = True
        else:
            line1, line2, line3 = (None,) * len(CONTACT_LINE_1), (None,) * len(CONTACT_LINE_2), (None,)
            shapes[f"CONTACT_{i}_ICON"].visible = False
            shapes[f"CONTACT_{i}_ICON"].marker = None

        for line, texts in enumerate((line1, line2, line3), start=1):
            for column, text in enumerate(texts):
                name = f"CONTACT_{i}_{line}_{column}"
                shapes[name].text = fitText(text, contactTextWidth[name])



def updateWeatherTicker(weather):       
    
    current = weather.current

    # Today's forecast, or an empty one (all blanks) if nothing has been fetched yet
    if weather.daily:
        today = weather.daily[0]
    else:
        today = wd.DailyWeather()

    message = [
        f"Updated {unix_to_datetime(weather.last_success)}",
        f"Sunrise {unix_to_hhmm(today.sunrise)}",
        f"Sunset {unix_to_hhmm(today.sunset)}",
        f"Daylight Duration {seconds_to_hours(today.daylight_duration)}",
        f"Sunshine Duration {seconds_to_hours(today.sunshine_duration)}",
        f"Temperature Range {num(today.temperature_min)} - {num(today.temperature_max)} {DEG}C",
        f"Air Pressure {num(current.pressure, '{:.0f}')} mb",
        f"Daily Precipitation {num(today.precipitation)} mm",
        f"Probability of rain {num(today.precipitation_probability, '{:.0f}')} %",
    ]

    shapes["SRS_TICKER"].texts = message


def updateGraphs(weather):

    # One list per graph line, all in step with the list of times
    times = []
    temperatures = []
    rainfalls = []
    pressures = []

    graphEnd = weather.hourly[0].time + GRAPH_DAYS * 24 * 3600 if weather.hourly else 0

    for hour in weather.hourly:
        if hour.time >= graphEnd:
            break

        times.append(hour.time)
        temperatures.append(hour.temperature)
        rainfalls.append(hour.precipitation)
        pressures.append(hour.pressure)

    shapes["GRAPH_TEMP"].timestamps = times
    shapes["GRAPH_TEMP"].values = temperatures

    shapes["GRAPH_RAIN"].timestamps = times
    shapes["GRAPH_RAIN"].values = rainfalls

    shapes["GRAPH_PRES"].timestamps = times
    shapes["GRAPH_PRES"].values = pressures



# Turn the weather titles red if the weather is old, i.e. the last fetch that
# worked was more than WEATHER_STALE_SECONDS ago. Before the first successful
# fetch there is nothing to flag, so the titles keep their normal colour.
def updateStaleFlag(weather):
    colour = borderColour1

    if weather.last_success is not None:
        if time.time() - weather.last_success > WEATHER_STALE_SECONDS:
            colour = ls.Colours.RED

    setColour(shapes["SHORT_RANGE_SCAN"], colour)
    setColour(shapes["LONG_RANGE_SCAN"], colour)



# Refresh every weather shape. A bad or missing field shouldn't be able to
# take the whole display down, so any error is printed and the shapes just
# keep whatever they showed before.
def refreshWeatherDisplay(weather):
    try:
        updateStaleFlag(weather)
        updateShortRangeScan(weather)
        updateLongRangeScan(weather)
        updateForecast(weather)
        updateGraphs(weather)
        updateWeatherTicker(weather)
    except Exception:
        print("Error updating weather display")
        traceback.print_exc()






# ---- TEMPORARY TEST CODE: see TEST_AIRCRAFT ----

# Where a made-up aircraft is `seconds` after the start of its flight: starts at that bearing and
# distance from the receiver and flies on in a straight line at its track and speed.
# Returns (latitude, longitude).
def testPosition(bearing, distance, track, speed, seconds):
    miles = speed * seconds / 3600
    north = distance * math.cos(math.radians(bearing)) + miles * math.cos(math.radians(track))
    east = distance * math.sin(math.radians(bearing)) + miles * math.sin(math.radians(track))

    latitude = ac.HOME_LAT + north / 60
    longitude = ac.HOME_LON + east / (60 * math.cos(math.radians(ac.HOME_LAT)))
    return latitude, longitude


# The made-up aircraft there are `seconds` into the cycle, as an AircraftData, nearest first
def testAircraftData(seconds):
    planes = []

    for (callsign, icao, category, squawk, military, bearing, distance,
         track, speed, altitude, climb, appears, leaves) in TEST_PLANES:
        if not appears <= seconds < leaves:
            continue

        latitude, longitude = testPosition(bearing, distance, track, speed, seconds - appears)
        planeDistance, planeBearing = ac.distance_and_bearing(ac.HOME_LAT, ac.HOME_LON, latitude, longitude)

        plane = ac.Aircraft()
        plane.icao = icao
        plane.callsign = callsign
        plane.on_ground = False
        plane.altitude_ft = altitude
        plane.speed_kt = speed
        plane.track_deg = track
        plane.vertical_rate_fpm = climb
        plane.latitude = latitude
        plane.longitude = longitude
        plane.distance_nm = planeDistance
        plane.bearing_deg = planeBearing
        plane.squawk = squawk
        plane.category = category
        plane.military = military
        plane.service = ac.service_for_callsign(callsign)
        planes.append(plane)

    planes.sort(key=operator.attrgetter("distance_nm"))

    data = ac.AircraftData()
    data.load(planes)
    return data


# Stands in for the AircraftFetcher: reports the made-up aircraft every TEST_POLL_SECONDS
class TestAircraftFetcher:

    def __init__(self):
        self._started = time.time()
        self._reported = 0
        self._data = ac.AircraftData()

    def start(self):
        return self

    def stop(self):
        pass

    def get_aircraft(self):
        now = time.time()

        if now - self._reported >= TEST_POLL_SECONDS:
            self._data = testAircraftData((now - self._started) % TEST_CYCLE_SECONDS)
            self._reported = now

        return self._data

    def get_error(self):
        return None

# ---- end of the temporary test code ----



def format_gmtoff(offset_sec):
    sign = "+" if offset_sec >= 0 else "-"
    hours, remainder = divmod(abs(offset_sec), 3600)
    minutes = remainder // 60
    return f"UTC{sign}{hours:02d}:{minutes:02d}"




# Draw the whole screen's background and make all of its shapes, in the current colours. It
# is done again when the colours change, so what is already there is thrown away first.
def buildInterface(background):
    background.fill(ls.Colours.BACKGROUND)
    shapes.clear()
    contactTextWidth.clear()

    buildBackground(background)

    # The Captain's Log is on the left of the right-hand side, and the Chronometer is up against
    # the right edge. The log takes the width that the Chronometer leaves.
    chronoX = HEADER_RIGHT_END - chronometerWidth()
    buildChronometer(background, chronoX, 75)
    buildCaptainsLog(background, RIGHT_AREA_X, 75, chronoX - LOG_CHRONO_GAP - RIGHT_AREA_X)
    buildShortRangeScan(background, 200, 75)
    buildForecast(background, 200, 374)
    buildLongRangeScan(background, 200, 570)
    buildGraphs(background, 200, 1040)
    buildRadar(background, RIGHT_AREA_X, 400)

    shapes["SRS_TICKER"] = ls.Ticker(background, 200, 534, 3 * GRAPH_WIDTH + 2 * GRAPH_GAP, 20, ls.Colours.BACKGROUND, None, fonts.TextSize.SMALL)

    print(f"Shape Count = {len(shapes)}")



# The LCARS screen. Its data (the time, calendar, aircraft and weather) is kept up to date,
# and the alerts are raised, even while another screen is shown, so nothing is missed and
# it is all there when it comes back. Only the animation and drawing stop while it is hidden.
class LcarsScreen(scr.Screen):

    name = "LCARS"
    hasSound = True

    def soundList(self):
        return [(s, 1.0) for s in sound.sounds.values()]

    # The alarms are silent while its sound is off
    def setSound(self, on):
        sound.muted = not on

    def start(self):
        global weatherIcons

        sound.initSound()

        self.lastUnixTime = -1
        self.lastminuteIndex = -1
        self.lastWeatherCount = -1
        self.lastCPUUpdate = -1
        self.lastHourKey = None      # the day and hour of the colour scheme in use, see update

        self.background = pygame.Surface((scr.SCREEN_WIDTH, scr.SCREEN_HEIGHT))
        self.background.fill(ls.Colours.BACKGROUND)

        buildInterface(self.background)

        weatherIcons = load_icons(ICON_FOLDER, (ICON_SIZE_SMALL, ICON_SIZE_LARGE))
        lw.start_weather_thread()

        self.calendar = lc.CalendarFetcher(max_events=CALENDAR_EVENT_COUNT)
        self.calendar.start()

        if TEST_AIRCRAFT:       # TEMPORARY TEST CODE
            self.aircraft = TestAircraftFetcher().start()
        else:
            self.aircraft = ac.AircraftFetcher()
            self.aircraft.start()

        self.routeFetcher = lk.Lookup(lk.ROUTE_URL, lk.make_route).start()
        self.modelFetcher = lk.Lookup(lk.MODEL_URL, lk.make_model).start()

        self.contactFirstSeen = {}       # the aircraft in range: icao -> (name, time it came in), see contactEvents
        self.firstPoll = True
        self.raisedAlerts = {}           # the alerts each aircraft has raised, see newAlerts
        self.alarmState = {"nextAlarm": 0}
        self.popup = ls.Popup(scr.SCREEN_WIDTH // 2, POPUP_CENTRE_Y)

        self.timerCount = 0
        self.timerTotal = 0
        self.timerMax = 0


    # A new colour scheme: the screen is built again in new colours, and everything on it is
    # filled in afresh by the updates in update()
    def newColours(self):
        chooseColours()
        buildInterface(self.background)
        self.lastUnixTime = -1
        self.lastminuteIndex = -1
        self.lastCPUUpdate = -1


    # The OK button (or Enter) changes the colour scheme
    def handleEvent(self, event):
        if event.type == scr.OK_PRESSED or (event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_SPACE)):
            self.newColours()


    def update(self, visible):
        frameStart = time.perf_counter()

        currentUnixTime = int(time.time())
        currentLocalTime = time.localtime(currentUnixTime)


        # On the hour the colour scheme changes (and when the OK button is pressed, see handleEvent)
        hourKey = (currentLocalTime.tm_yday, currentLocalTime.tm_hour)
        if hourKey != self.lastHourKey:
            if self.lastHourKey is not None:
                self.newColours()

            self.lastHourKey = hourKey


        # Updates every second
        if currentUnixTime != self.lastUnixTime:
            shapes["UNIXTIME"].text = f"TIMESTAMP    {currentUnixTime}"
            self.lastUnixTime = currentUnixTime


            shapes["CHRONO_SEC"].text = f"{currentLocalTime.tm_sec:02d}"
            shapes["CHRONO_MIN"].text = f"{currentLocalTime.tm_min:02d}"
            shapes["CHRONO_HOUR"].text = f"{currentLocalTime.tm_hour:02d}"
            shapes["CHRONO_SECONDS"].level = currentLocalTime.tm_sec + 1

            unixTimeTuple = time.gmtime(currentUnixTime)
            secondOfDay = unixTimeTuple.tm_hour * 3600 + unixTimeTuple.tm_min * 60 + unixTimeTuple.tm_sec
            thousandthOfDay = secondOfDay * 1000 / 86400
            shapes["STARDATE"].text = f"STARDATE    {currentLocalTime.tm_year%1000:03d}." + \
                                      f"{unixTimeTuple.tm_yday:03d}.{thousandthOfDay:03.01f}"

            if currentLocalTime.tm_sec % 2:
                shapes["CHRONO_COLON1"].text = ":"
            else:
                shapes["CHRONO_COLON1"].text = " "

            if (currentLocalTime.tm_sec % 8) < 4:
                tz = "BST" if currentLocalTime.tm_isdst == 1 else "GMT"
                shapes["CHRONO_TIMEZONE"].text = tz
            else:
                shapes["CHRONO_TIMEZONE"].text = format_gmtoff(currentLocalTime.tm_gmtoff)

            # Update captains Log with google calendar
            updateCaptainsLog(self.calendar, currentUnixTime)

            # Announce the aircraft that have come into range or gone out of it, and update
            # the list of the nearest ones (the radar is updated every frame, below)
            planes = emergenciesFirst(self.aircraft.get_aircraft().aircraft)
            for text in contactEvents(self.contactFirstSeen, planes, time.time(), self.firstPoll):
                shapes["LCARS_STATUS"].message(text)

            self.firstPoll = False
            emergencies, military, services = newAlerts(self.raisedAlerts, planes)
            raiseAlerts(emergencies, military, services, self.popup, self.alarmState)
            updateAircraftList(planes, self.routeFetcher, self.modelFetcher)
            updateSearching(planes, self.aircraft.get_error())

        # Every frame: the aircraft move on a little, and a new one blinks. Only while
        # it is shown, as no one would see it; the alarm sounds either way.
        now = time.time()
        if visible:
            planes = updateRadar(self.aircraft, self.contactFirstSeen, now)
            colourAircraftList(planes, self.contactFirstSeen, now)
        repeatEmergencyAlarm(self.popup, self.alarmState, now)


        # Updates every minute or when the weather thread has new data. (The weather thread
        # bumps a counter after each successful fetch. Drawing must stay on this thread,
        # so the loop watches the counter.)
        minuteIndex = currentUnixTime // 60
        weatherCount = lw.get_update_count()
        if (minuteIndex != self.lastminuteIndex) or (weatherCount != self.lastWeatherCount):
            weather = lw.get_weather()
            shapes["CHRONO_DATE"].text = time.strftime("%a %d %b %Y", currentLocalTime)
            refreshWeatherDisplay(weather)
            self.lastminuteIndex = minuteIndex
            self.lastWeatherCount = weatherCount


        # Redraw any shape which has changed since the last frame. Not while it is hidden:
        # the shapes that change meanwhile remember it, and are redrawn when it is shown again.
        if visible:
            for shape in shapes.values():
                shape.update()

            # The time this took, for the CPU Usage (only the frames when it is shown)
            elapsed = time.perf_counter() - frameStart
            self.timerMax = max(self.timerMax, elapsed)
            self.timerTotal += elapsed
            self.timerCount += 1


        # Update the CPU Usage
        if currentUnixTime >= (self.lastCPUUpdate + CPU_RATE) and self.timerCount > 0:

            timerAverage = self.timerTotal/self.timerCount
            used, free, total = memory_usage_mb()

            cpuText = f"Draw Time: {timerAverage*1000:.2f} ms (Max: {self.timerMax*1000:.2f} ms)"
            memoryText = f"Using {used:.1f} MB of {total:.0f} MB"
            shapes["LCARS_STATUS"].texts  = [cpuText, memoryText]

            self.timerCount = 0
            self.timerMax = 0.0
            self.timerTotal = 0.0

            self.lastCPUUpdate = currentUnixTime


    def draw(self, surface):
        surface.blit(self.background, (0, 0))
        self.popup.draw(surface)
