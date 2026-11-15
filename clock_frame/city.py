"""
city.py

A view across a street in a city that is made up afresh each time the program starts (or the
same one each time, with CITY_SEED): three rows of buildings going back into the haze, with
a pavement, street lamps and trees, and a road in front. The time is in the top right corner.

The sky is worked out from where the sun really is, for WEATHER_LAT and WEATHER_LON (from
my_settings.py): blue by day, gold and pink around sunset, deep blue at dusk and dark at night,
with the stars coming out and the moon (in its right phase, and in its right place) crossing
it. The buildings are lit by the same light, and fade into the sky behind as they go back.

As it gets dark the street lamps come on, one by one, and so do the windows: homes in the
evening until their people go to bed (and again early in the morning), offices until their
workers go home, shops until they close. A few stay on all night.

Gentle things happen all the time: clouds drift across (more on some days than others), cars
vans, taxis and buses go by (keeping left, CITY_DRIVE_ON_LEFT), braking for each other, with their
lights on after dark, people walk along the pavement, a flock of
birds or a high aeroplane crosses the sky now and then, steam rises from vents on the roofs,
the red lights on the tallest masts glow and fade, a television flickers in a window, the
stars twinkle and the colon of the clock breathes, once every two seconds.

The light is the sun's: the sides of the buildings that face it are lit (warm at either end
of the day), the window panes reflect the sky, lit windows and lamps throw their light on the
walls and the damp road, and the clouds are lit from the sun's side. The walls are brick, stone
or concrete, streaked by the rain.

A new city is made each night at CITY_NEW_CITY_HOUR. The TIME button (or T, or a tap on the
clock) shows it an hour later each press, to see it at other times of day; holding TIME (or R)
goes back to now, as it does by itself after CITY_PREVIEW_SECONDS.

A distant church bell strikes the hours (CITY_STRIKE_HOURS). There are no ticks.
"""

import datetime
import math
import os
import threading
import time
import pygame
import pygame.gfxdraw
import numpy as np
import screens as scr
import fonts
import synth
from .common import Face, smoothstep, toSurface, waves, bellStroke, makeSound, SANS_FONTS
from . import vehicles

##==================================================================
## SETTINGS (they are in settings.py, next to lcars.py)
##==================================================================

from settings import (
    CITY_SEED as SEED,
    CITY_HOURS_24 as HOURS_24,
    CITY_STRIKE_HOURS as STRIKE_HOURS,
    CITY_FACING as FACING,
    CITY_VIEW_WIDTH as VIEW_WIDTH,
    CITY_CLOUDINESS as CLOUDINESS,
    CITY_TRAFFIC as TRAFFIC,
    CITY_PEOPLE as PEOPLE,
    CITY_STREET_Y as STREET_Y,
    CITY_CLOCK_RIGHT as CLOCK_RIGHT,
    CITY_CLOCK_TOP as CLOCK_TOP,
    CITY_CLOCK_SIZE as CLOCK_SIZE,
    CITY_DATE_SIZE as DATE_SIZE,
    CITY_CLOCK_COLOUR as CLOCK_COLOUR,
    CITY_TEXT_COLOUR as TEXT_COLOUR,
    CITY_NEW_CITY_HOUR as NEW_CITY_HOUR,
    CITY_PREVIEW_SECONDS as PREVIEW_SECONDS,
    CITY_PREVIEW_COLOUR as PREVIEW_COLOUR,
    CITY_DRIVE_ON_LEFT as DRIVE_ON_LEFT,
    WEATHER_LAT as LATITUDE,            # from my_settings.py
    WEATHER_LON as LONGITUDE,
)

W, H = scr.SCREEN_WIDTH, scr.SCREEN_HEIGHT
KERB_Y = STREET_Y + 42                  # the edge of the pavement
FAR_LANE_Y = KERB_Y + 58                # where the wheels of the cars going left touch the road...
NEAR_LANE_Y = KERB_Y + 132              # ...and those going right
MARKING_Y = KERB_Y + 88                 # the dashed line down the middle
LANE_DIRECTION = {0: 1, 1: -1} if DRIVE_ON_LEFT else {0: -1, 1: 1}     # which way each lane goes (1: right)
LANE_SCALE = {0: 0.98, 1: 1.12}         # the near lane is a little bigger, being nearer
VIEW_X = np.linspace(-120, 2040, 9)     # each vehicle is seen in 3D from where it is at each of these across the screen
HORIZON_Y = STREET_Y - 30               # your eye level, where the sun sets behind the buildings
VANISH = (W / 2, HORIZON_Y)             # where the sides of the buildings go back towards
ALT_SCALE = 760                         # how high the sun and moon go, in pixels (see skyPoint)
REFRESH_SECONDS = 15                    # the sky and the light on the city are worked out again this often

SMALL = 8                               # the sky is worked out this many times smaller, then made smooth
SW, SH = W // SMALL, H // SMALL


##==================================================================
## THE SUN AND THE MOON
##==================================================================

# Days since noon on 1 January 2000 (J2000), from a Unix time
def j2000(ts):
    return ts / 86400.0 + 2440587.5 - 2451545.0


# Altitude and azimuth (degrees, from north going east) of a body at right ascension ra and
# declination dec (radians), seen from LATITUDE and LONGITUDE
def horizontal(ra, dec, d):
    lat = math.radians(LATITUDE)
    gmst = math.radians((280.46061837 + 360.98564736629 * d) % 360)
    ha = gmst + math.radians(LONGITUDE) - ra
    alt = math.asin(math.sin(lat) * math.sin(dec) + math.cos(lat) * math.cos(dec) * math.cos(ha))
    az = math.atan2(math.sin(ha), math.cos(ha) * math.sin(lat) - math.tan(dec) * math.cos(lat))
    return math.degrees(alt), (math.degrees(az) + 180) % 360


def equatorial(lon, lat, d):
    e = math.radians(23.439 - 3.6e-7 * d)
    ra = math.atan2(math.sin(lon) * math.cos(e) - math.tan(lat) * math.sin(e), math.cos(lon))
    dec = math.asin(math.sin(lat) * math.cos(e) + math.cos(lat) * math.sin(e) * math.sin(lon))
    return ra, dec


# Where the sun and the moon are at Unix time ts, as (altitude, azimuth) each, and how far
# apart they are (radians: 0 at new moon, pi at full moon). Good to a degree or so.
def sunAndMoon(ts):
    d = j2000(ts)
    g = math.radians(357.529 + 0.98560028 * d)
    sunLon = math.radians(280.459 + 0.98564736 * d + 1.915 * math.sin(g) + 0.020 * math.sin(2 * g))
    sun = horizontal(*equatorial(sunLon, 0.0, d), d)

    m = math.radians(134.963 + 13.064993 * d)
    f = math.radians(93.272 + 13.229350 * d)
    moonLon = math.radians(218.316 + 13.176396 * d + 6.289 * math.sin(m))
    moonLat = math.radians(5.128 * math.sin(f))
    moon = horizontal(*equatorial(moonLon, moonLat, d), d)

    elongation = math.acos(max(-1.0, min(1.0, math.cos(moonLon - sunLon) * math.cos(moonLat))))
    return sun, moon, elongation


# Where something at this altitude and azimuth is on the screen: the middle of the screen is
# CITY_FACING, VIEW_WIDTH degrees across it. Heights are squashed, so that the whole sky
# fits above the buildings.
def skyPoint(alt, az):
    off = (az - FACING + 180) % 360 - 180
    x = W / 2 + off * W / VIEW_WIDTH
    y = HORIZON_Y - math.copysign(ALT_SCALE * (1 - math.exp(-abs(alt) / 22)), alt)
    return x, y


# How dark it is, 0 by day to 1 at night, from the sun's altitude
def darknessFor(sunAlt):
    return float(smoothstep(4.0, -7.0, sunAlt))


##==================================================================
## THE COLOURS OF THE SKY, BY THE SUN'S ALTITUDE
##==================================================================

# sun altitude: the sky at the top, the sky at the horizon, the glow around the sun, the light
# on the buildings, and the clouds where the light falls on them and in their own shade (at
# night they are lit from below, by the city)
SKY_KEYS = [
    (-90, (3, 5, 14),     (13, 15, 30),    (0, 0, 0),       (36, 40, 62),    (54, 44, 50),    (22, 24, 38)),
    (-18, (3, 5, 14),     (13, 15, 30),    (0, 0, 0),       (36, 40, 62),    (54, 44, 50),    (22, 24, 38)),
    (-12, (6, 9, 26),     (22, 25, 50),    (24, 10, 18),    (44, 48, 76),    (62, 50, 62),    (28, 28, 46)),
    (-8,  (12, 18, 50),   (54, 48, 86),    (90, 34, 36),    (64, 64, 98),    (124, 76, 90),   (50, 44, 70)),
    (-4,  (26, 40, 92),   (150, 92, 98),   (190, 84, 54),   (118, 100, 126), (240, 120, 92),  (106, 78, 102)),
    (-1,  (44, 64, 128),  (236, 134, 82),  (255, 140, 60),  (186, 140, 128), (255, 162, 100), (150, 106, 118)),
    (2,   (58, 92, 166),  (250, 176, 112), (255, 172, 92),  (232, 172, 134), (255, 214, 168), (178, 144, 148)),
    (6,   (64, 110, 190), (236, 206, 176), (255, 210, 152), (248, 212, 178), (255, 240, 220), (178, 172, 182)),
    (12,  (58, 114, 200), (196, 212, 230), (240, 228, 200), (255, 240, 224), (252, 250, 246), (170, 178, 194)),
    (25,  (48, 108, 204), (172, 204, 236), (200, 200, 188), (255, 249, 240), (255, 255, 255), (168, 178, 198)),
    (90,  (40, 100, 200), (160, 198, 236), (180, 180, 170), (255, 252, 248), (255, 255, 255), (168, 178, 198)),
]
SKY_TABLE = np.array([[k[0]] + [c for colour in k[1:] for c in colour] for k in SKY_KEYS], np.float32)


def skyColours(sunAlt):
    row = np.array([np.interp(sunAlt, SKY_TABLE[:, 0], SKY_TABLE[:, i]) for i in range(1, SKY_TABLE.shape[1])], np.float32)
    names = ("zenith", "horizon", "glow", "ambient", "cloudLit", "cloudShade")
    return {name: row[3 * i:3 * i + 3] for i, name in enumerate(names)}


# Brightens a colour by another, like light falling on it, without going past white
def screenBlend(a, b):
    return 255 - (255 - a) * (255 - np.clip(b, 0, 255)) / 255


##==================================================================
## THE BUILDINGS
##==================================================================

# Each style of building: its colours, its windows (wide, high and apart, as fractions of a
# floor), whether its windows have sashes and its top a cornice, and who is inside
STYLES = {
    "brick":    dict(colours=[(146, 76, 56), (126, 66, 50), (160, 94, 70), (112, 62, 50), (138, 88, 66), (150, 104, 80)],
                     win=(0.36, 0.56, 0.78), sash=True, cornice=True, kinds=["home"] * 4 + ["office"]),
    "stone":    dict(colours=[(196, 184, 160), (182, 172, 152), (204, 196, 178), (170, 162, 148), (190, 170, 140)],
                     win=(0.40, 0.60, 0.84), sash=True, cornice=True, kinds=["home", "home", "office"]),
    "concrete": dict(colours=[(150, 150, 146), (134, 136, 140), (166, 160, 150), (120, 124, 128)],
                     win=(0.56, 0.46, 0.80), sash=False, cornice=False, kinds=["home", "home", "office"]),
    "glass":    dict(colours=[(74, 98, 120), (62, 86, 100), (88, 110, 126), (56, 74, 94), (80, 96, 104)],
                     win=(0.52, 0.86, 0.56), sash=False, cornice=False, kinds=["office"]),
    "dark":     dict(colours=[(70, 70, 78), (58, 62, 70), (84, 80, 76)],
                     win=(0.72, 0.42, 0.80), sash=False, cornice=False, kinds=["office"]),
    "deco":     dict(colours=[(196, 180, 150), (184, 170, 146), (170, 160, 150)],
                     win=(0.30, 0.64, 0.62), sash=False, cornice=True, kinds=["office", "home"]),
}

# The three rows, from the back: how high a floor is, how high and wide the buildings are,
# how often there is a gap between them, which styles, how much haze is in front of them and
# how far their sides go back
ROWS = [
    dict(floor=24, minH=270, maxH=600, towerH=740, towerChance=0.14, minW=50, maxW=130, gapChance=0.35, maxGap=26,
         styles={"brick": 1, "stone": 1.5, "concrete": 2, "glass": 2, "dark": 1, "deco": 1.2}, haze=0.5, depth=0.015),
    dict(floor=36, minH=210, maxH=500, towerH=620, towerChance=0.08, minW=80, maxW=180, gapChance=0.3, maxGap=40,
         styles={"brick": 2, "stone": 2, "concrete": 1.5, "glass": 1.5, "dark": 1, "deco": 1}, haze=0.24, depth=0.03),
    dict(floor=50, minH=150, maxH=400, towerH=0, towerChance=0, minW=130, maxW=270, gapChance=0.18, maxGap=46,
         styles={"brick": 3, "stone": 2.5, "concrete": 1, "glass": 0.6, "dark": 0.5}, haze=0.0, depth=0.05),
]
SHOP_FLOOR = 64                         # the height of the shops at the foot of the front row
MATERIALS = {"brick": 1, "stone": 2, "deco": 2, "concrete": 3, "dark": 3, "glass": 0}

HOME, OFFICE, SHOP, SIGN, STAIR = range(5)
SIGN_COLOURS = [(170, 30, 40), (30, 90, 60), (24, 48, 110), (200, 140, 30), (90, 40, 110), (20, 20, 24), (180, 70, 30)]
AWNING_COLOURS = [(150, 30, 34), (30, 80, 50), (30, 50, 100), (190, 120, 30), (60, 60, 64)]


class Building:
    def __init__(self, x0, x1, top, style, colour):
        self.x0, self.x1, self.top = x0, x1, top
        self.style = style
        self.colour = np.array(colour, np.float32)
        self.extras = []                # the parts above the roof that light can be put on


class Window:
    __slots__ = ("rect", "lit", "kind", "threshold", "a", "b", "home", "group", "seed", "period", "on", "layer",
                 "glow", "glowRect", "near")

    def __init__(self, rect, lit, kind, layer, rng, group=None):
        self.rect = rect
        self.lit = lit                  # its picture with the light on
        self.kind = kind
        self.layer = layer
        self.group = group              # a floor of offices, which go home together
        self.seed = int(rng.integers(1, 2 ** 31))
        self.on = False
        self.glow = None                # the light it throws on the wall round it (for adding)...
        self.glowRect = rect            # ...and where
        self.near = []                  # the windows whose light overlaps its
        self.threshold = float(rng.uniform(0.2, 0.85))      # how dark it must be for the light to go on
        self.period = float(rng.uniform(5, 16))             # minutes: rooms are left and come back to
        self.a = self.b = self.home = 0
        if kind == HOME:
            if rng.random() < 0.45:
                self.home = rng.uniform(270, 450)           # out at work until between half past four and half past seven
            # bedtime and getting up, in minutes after noon
            r = rng.random()
            if r < 0.1:
                self.a = rng.uniform(540, 610)              # early to bed
            elif r < 0.18:
                self.a = rng.uniform(870, 1000)             # night owls
            else:
                self.a = float(np.clip(rng.normal(675, 70), 560, 880))
            self.b = float(np.clip(rng.normal(1125, 35), 1035, 1200)) if rng.random() < 0.65 else 2000
        elif kind in (SHOP, SIGN):
            self.a = rng.uniform(1200, 1290)                # opening...
            self.b = rng.uniform(330, 600)                  # ...and closing
            if rng.random() < 0.06:
                self.a, self.b = 0, 1440                    # open all night
        elif kind == STAIR:
            self.threshold = float(rng.uniform(0.15, 0.4))


# A small whole-number hash of two numbers, as a fraction 0 to 1, for choices that change now
# and then but are the same each time they are asked
def chance(seed, slot):
    h = (seed * 2654435761 + int(slot) * 40503 + 12345) & 0xFFFFFFFF
    h ^= h >> 15
    h = (h * 2246822519) & 0xFFFFFFFF
    h ^= h >> 13
    return h / 4294967296.0


##==================================================================
## DRAWING HELPERS
##==================================================================

def shade(colour, k):
    return tuple(int(max(0, min(255, c * k))) for c in colour)


def aaPolygon(surface, colour, points):
    points = [(round(x), round(y)) for x, y in points]
    pygame.gfxdraw.filled_polygon(surface, points, colour)
    pygame.gfxdraw.aapolygon(surface, points, colour)


# A glowing spot, for adding to what is under it: a bright middle and a soft halo
def glowSprite(radius, colour, core=0.25, power=1.0):
    size = int(radius * 2)
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    r = np.hypot(xx - radius + 0.5, yy - radius + 0.5) / radius
    level = (np.exp(-(r / core) ** 2) + 0.35 * np.exp(-r * 4)) * np.clip(1 - r, 0, 1) * power
    rgb = np.array(colour, np.float32) * level[..., None]
    return toSurface(rgb).convert()


# Smooth random noise, 0 to 1, h x w: a grid of random numbers cell pixels apart, blended
def valueNoise(h, w, cell, rng):
    grid = rng.random((int(h / cell) + 2, int(w / cell) + 2)).astype(np.float32)
    y = np.arange(h, dtype=np.float32) / cell
    x = np.arange(w, dtype=np.float32) / cell
    y0, x0 = y.astype(int), x.astype(int)
    fy, fx = y - y0, x - x0
    fy, fx = (fy * fy * (3 - 2 * fy))[:, None], (fx * fx * (3 - 2 * fx))[None, :]
    rows0, rows1 = grid[y0], grid[y0 + 1]
    top = rows0[:, x0] + (rows0[:, x0 + 1] - rows0[:, x0]) * fx
    bottom = rows1[:, x0] + (rows1[:, x0 + 1] - rows1[:, x0]) * fx
    return top + (bottom - top) * fy


# Noise with detail at several sizes, from cell pixels down, 0 to 1 (about 0.5 on average)
def fractal(h, w, cell, octaves, rng):
    total = np.zeros((h, w), np.float32)
    amount, weight = 1.0, 0.0
    for _ in range(octaves):
        total += amount * valueNoise(h, w, max(1.0, cell), rng)
        weight += amount
        amount *= 0.5
        cell /= 2
    return total / weight


# Darker towards the corners, as a camera's lens makes it: a picture to multiply by
def vignetteSurface():
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.hypot((xx - W / 2) / (W / 2), (yy - H / 2) / (H / 2))
    level = 255 * (1 - 0.24 * smoothstep(0.55, 1.45, r))
    return toSurface(np.repeat(level[..., None], 3, axis=2)).convert()


# The soft light a lit window throws on the wall round it, g pixels each way, for adding
def windowGlow(lit, g, strength):
    w, h = lit.get_size()
    colour = np.array(pygame.transform.average_color(lit)[:3], np.float32)
    yy, xx = np.mgrid[0:h + 2 * g, 0:w + 2 * g].astype(np.float32)
    dx = np.maximum(0, np.maximum(g - xx, xx - (g + w - 1)))
    dy = np.maximum(0, np.maximum(g - yy, yy - (g + h - 1)))
    level = strength * np.clip(1 - np.hypot(dx, dy) / g, 0, 1) ** 2.2
    level *= 1 + 0.3 * (yy > g + h)                     # a little more on the sill below
    return toSurface(colour * level[..., None]).convert()


# A copy of a picture with its colours multiplied by colour (0-255 each), keeping its alpha
def tinted(image, colour):
    image = image.copy()
    image.fill(tuple(int(max(0, min(255, c))) for c in colour), special_flags=pygame.BLEND_RGB_MULT)
    return image


##==================================================================
## THE FACE
##==================================================================

class CityFace(Face):

    name = "CITY"
    statusColour = TEXT_COLOUR
    statusFonts = SANS_FONTS

    def build(self, chimeVolume, tickVolume):
        self.makeClockFonts()
        stroke = bellStroke(277, 5.5, decayScale=1.3, hammer=0.03)
        stroke = synth.smooth(stroke, 4) * 0.8          # a long way off: softer, and the top taken off
        self.bell = makeSound(stroke, chimeVolume * 0.8)
        self.vignette = vignetteSurface()
        self.offset = 0.0               # seconds ahead of the real time, while looking at another time of day...
        self.previewUntil = 0.0         # ...until this (time.monotonic)
        # the vehicles take a while to make, so they are made by a thread of their own, joining
        # the traffic as each is ready, and kept from night to night
        self.carModels = []
        self.newModels = []
        self.vehicleLight = None
        self.makeCity()
        self.vehicleThread = threading.Thread(target=self.makeCars, name="city vehicles", daemon=True)
        self.vehicleThread.start()

    # The city: all of it made up afresh (each night, see housekeeping)
    def makeCity(self):
        seed = SEED if SEED is not None else int(time.time() * 1000) % (2 ** 31)
        self.rng = np.random.default_rng(seed)
        print(f"City: seed {seed}")
        started = time.monotonic()

        self.windows = []
        self.beacons = []               # the red lights on the masts: (x, y)
        self.vents = []                 # where steam comes out: (x, y)
        self.lamps = []                 # the street lamps' heads: (x, y, how dark before they come on)
        self.sideFaces = []             # the sides of the buildings, which the sun may fall on
        self.floors = {}
        self.spriteCache = {}
        self.layers = self.drawRows()
        self.layers.append(self.drawStreetThings())
        self.layers[2]["surface"] = self.drawStreet(self.layers[2]["surface"])
        for layer in self.layers:
            area = layer["surface"].get_bounding_rect()
            layer["surface"] = layer["surface"].subsurface(area).copy().convert_alpha()
            if layer.get("refl") is not None:
                layer["refl"] = layer["refl"].subsurface(area).copy()
            layer["offset"] = area.topleft
        self.cityTop = min(layer["offset"][1] for layer in self.layers)
        self.hideCoveredWindows()
        self.mergeRows()
        self.extractSides()
        self.findNeighbours()
        self.layers = self.nearer = None

        self.stars, self.twinkles = self.makeStars()
        self.dither = self.makeDither()
        self.sunImage = self.makeSun()
        self.moonGlow = glowSprite(150, (70, 76, 96), core=0.12)
        self.moonKey = None
        self.clouds = []
        self.cloudShapes = [self.makeCloudShape(i) for i in range(10)]
        self.lampGlow = self.makeLampGlow()
        self.beaconGlows = [glowSprite(14, (255, 40, 30), power=k / 7) for k in range(8)]
        self.headGlow = glowSprite(14, (255, 244, 220), core=0.3)
        self.tailGlow = glowSprite(9, (255, 30, 20), core=0.35, power=0.9)
        self.beam = self.makeBeam()
        self.strobe = glowSprite(10, (255, 255, 255), core=0.25)
        self.navRed = glowSprite(7, (255, 50, 40), core=0.3)
        self.puffs = self.makePuffs()
        self.walkers = self.makeWalkers()
        self.contrail = self.makeContrail()
        self.tv = [w for w in self.windows if w.kind == HOME and w.layer >= 1]
        self.tv = [self.tv[i] for i in self.rng.choice(len(self.tv), min(7, len(self.tv)), replace=False)] if self.tv else []

        self.cars = []
        self.people = []
        self.steam = []
        self.flock = None
        self.plane = None
        self.nextFlock = time.monotonic() + self.rng.uniform(20, 90)
        self.nextPlane = time.monotonic() + self.rng.uniform(15, 60)
        self.state = None
        self.stateTime = None
        self.lastT = None
        self.clockKey = None
        self.windowsDue = 0
        self.lightKey = None
        self.glowsOn = False
        self.litLamps = []
        self.city = None
        self.job = None
        self.cityDay = self.dayOf(datetime.datetime.now())
        print(f"City: built in {time.monotonic() - started:.1f}s")

    # The day a city belongs to: a new one starts at NEW_CITY_HOUR
    @staticmethod
    def dayOf(now):
        return (now - datetime.timedelta(hours=NEW_CITY_HOUR or 0)).date()

    # Every frame, shown or not: a new city when a new day starts (at NEW_CITY_HOUR, in the
    # middle of the night, as making one holds everything up for a few seconds)
    def housekeeping(self, now):
        if NEW_CITY_HOUR is not None and SEED is None and self.dayOf(now) != self.cityDay:
            print("City: a new day, so a new city")
            self.makeCity()

    # The TIME button (or T, or a tap on the clock) shows the city an hour later than the one
    # shown; holding it down (or R) goes back to now. It goes back by itself after
    # PREVIEW_SECONDS. Returns the words of the notice to show.
    def handleEvent(self, event):
        later = (event.type == scr.TIME_PRESSED or (event.type == pygame.KEYDOWN and event.key == pygame.K_t) or
                 (event.type == pygame.MOUSEBUTTONDOWN and self.clockRect().collidepoint(event.pos)))
        back = event.type == scr.TIME_HELD or (event.type == pygame.KEYDOWN and event.key == pygame.K_r)
        if not (later or back):
            return None
        real = datetime.datetime.now()
        offset = 0.0
        if later:
            shown = real + datetime.timedelta(seconds=self.offset)
            target = shown.replace(minute=0, second=0, microsecond=0) + datetime.timedelta(hours=1)
            offset = (target - real).total_seconds()
            if offset > 23.5 * 3600:            # all the way round the day: back to now
                offset = 0.0
        self.offset = offset
        self.previewUntil = time.monotonic() + PREVIEW_SECONDS
        self.stateTime = None                   # work out the sky again at once
        if not offset:
            return f"{self.name} NOW"
        target = real + datetime.timedelta(seconds=offset)
        return f"{self.name} AT {self.hourText(target)}"

    @staticmethod
    def hourText(at):
        if HOURS_24:
            return f"{at.hour:02d}:00"
        return f"{at.hour % 12 or 12}{'AM' if at.hour < 12 else 'PM'}"

    def clockRect(self):
        if self.clockKey is None:
            return pygame.Rect(0, 0, 0, 0)
        shadow, where, _, _ = self.clockImage
        return pygame.Rect(where, shadow.get_size())

    def sounds(self):
        return [self.bell]

    def chime(self, hour, minute):
        if minute != 0 or not STRIKE_HOURS:
            return []
        return [(i * 2.6, self.bell) for i in range(hour % 12 or 12)]

    def enter(self):
        self.lastT = None
        self.stateTime = None               # work out the sky again at once

    ##--------------------------------------------------------------
    ## Building the city, once
    ##--------------------------------------------------------------

    # Where the clock is, so that no building is tall enough to be behind it
    def clockClear(self):
        width = max(self.timeFont.size("00:00")[0], self.spacedWidth("WEDNESDAY 30 SEPTEMBER"))
        return CLOCK_RIGHT - width - 30, CLOCK_TOP + self.dateY + DATE_SIZE + 40

    def drawRows(self):
        rng = self.rng
        clearLeft, clearBottom = self.clockClear()
        layers = []
        for index, row in enumerate(ROWS):
            surface = pygame.Surface((W, H), pygame.SRCALPHA)
            surface.fill((0, 0, 0, 0))
            self.currentRefl = pygame.Surface((W, H)).convert()     # how much each window pane reflects the sky
            self.currentRefl.fill((0, 0, 0))
            self.currentIds = pygame.Surface((W, H)).convert()      # which side of a building each pixel is (0: none)
            self.currentIds.fill((0, 0, 0))
            self.facades = []
            first = len(self.windows)
            buildings = self.planRow(row, clearLeft, clearBottom)
            for b in buildings:
                self.drawSide(surface, b, row, index)
            for b in buildings:
                self.drawBuilding(surface, b, row, index)
            self.texture(surface, buildings, index, row, self.windows[first:])
            layers.append(dict(surface=surface, haze=row["haze"], refl=self.currentRefl, ids=self.currentIds))
        return layers

    def planRow(self, row, clearLeft, clearBottom):
        rng = self.rng
        styles = list(row["styles"])
        weights = np.array([row["styles"][s] for s in styles], np.float64)
        weights /= weights.sum()
        buildings = []
        x = -rng.uniform(10, row["maxW"] * 0.6)
        while x < W + 10:
            w = round(rng.uniform(row["minW"], row["maxW"]))
            height = row["minH"] + (row["maxH"] - row["minH"]) * rng.random() ** 1.3
            style = str(rng.choice(styles, p=weights))
            if rng.random() < row["towerChance"]:
                height = rng.uniform(row["maxH"], row["towerH"])
                style = str(rng.choice(["glass", "deco", "dark", "glass"]))
                w = round(rng.uniform(row["minW"], row["maxW"] * 0.85))
            top = STREET_Y - height
            if x + w > clearLeft:
                top = max(top, clearBottom + rng.uniform(10, 60))
            colour = np.array(STYLES[style]["colours"][rng.integers(len(STYLES[style]["colours"]))], np.float32)
            colour *= rng.uniform(0.9, 1.1)
            buildings.append(Building(round(x), round(x + w), round(top), style, colour))
            x += w
            if rng.random() < row["gapChance"]:
                x += rng.uniform(6, row["maxGap"])
        return buildings

    # The side of a building, going back towards the middle of the screen, seen above the one
    # next to it
    def drawSide(self, surface, b, row, layerIndex):
        k = row["depth"]
        if k <= 0:
            return
        middle = (b.x0 + b.x1) / 2
        onLeft = middle > W / 2             # we see its left side, which faces CITY_FACING - 90
        x = b.x0 if onLeft else b.x1
        top, bottom = b.top, STREET_Y
        a = (x, top)
        a2 = (x + k * (VANISH[0] - x), top + k * (VANISH[1] - top))
        c2 = (x + k * (VANISH[0] - x), bottom)
        points = [a, a2, c2, (x, bottom)]
        aaPolygon(surface, shade(b.colour, 0.5), points)      # in shade: the sun is added later, if it is on it
        code = len(self.sideFaces) + 1
        pygame.draw.polygon(self.currentIds, (code & 255, code >> 8, 0), [(round(px), round(py)) for px, py in points])
        xs = [px for px, _ in points]
        self.sideFaces.append(dict(code=code, layer=layerIndex, normal=(FACING - 90 if onLeft else FACING + 90) % 360,
                                   box=(math.floor(min(xs)) - 1, top - 1, math.ceil(max(xs)) + 2, bottom)))
        # a few dark slits of window on it, floor by floor
        f = row["floor"]
        width = abs(a2[0] - x)
        if width > 5:
            y = top + f * 0.6
            while y + f * 0.5 < bottom:
                x0, x1 = sorted((x + (a2[0] - x) * 0.3, x + (a2[0] - x) * 0.7))
                pygame.draw.rect(surface, shade(b.colour, 0.3), (round(x0), round(y), max(1, round(x1 - x0)), round(f * 0.5)))
                y += f

    def drawBuilding(self, surface, b, row, layerIndex):
        rng = self.rng
        style = STYLES[b.style]
        f = row["floor"]
        colour = tuple(int(c) for c in np.clip(b.colour, 0, 255))
        front = layerIndex == 2
        kind = str(rng.choice(style["kinds"]))
        kindCode = {"home": HOME, "office": OFFICE}[kind]
        if b.style in ("glass", "dark"):
            kindCode = OFFICE

        # the body, perhaps stepping back as it goes up, as the Art Deco towers do
        sections = [(b.x0, b.x1, b.top)]
        height = STREET_Y - b.top
        if b.style in ("deco", "glass") and height > 380 and rng.random() < 0.75:
            w = b.x1 - b.x0
            mid = (b.x0 + b.x1) / 2
            sections = [(b.x0, b.x1, round(b.top + height * 0.3))]
            sections.append((round(mid - w * 0.36), round(mid + w * 0.36), round(b.top + height * 0.12)))
            sections.append((round(mid - w * 0.22), round(mid + w * 0.22), b.top))

        for i, (x0, x1, top) in enumerate(sections):
            bottom = STREET_Y if i == 0 else sections[i - 1][2]
            pygame.draw.rect(surface, colour, (x0, top, x1 - x0, bottom - top))
            pygame.draw.rect(self.currentIds, (0, 0, 0), (x0 - 2, top, x1 - x0 + 4, bottom - top))
            self.facades.append((x0, top, x1, bottom, b.style))
            if b.style == "glass":
                self.drawCurtainWall(surface, b, x0, x1, top, bottom, f, layerIndex, front and i == 0)
            else:
                self.drawWindows(surface, b, x0, x1, top, bottom, f, layerIndex, kindCode, front and i == 0)
            if style["cornice"]:
                depth = max(3, round(f * 0.22))
                pygame.draw.rect(surface, shade(colour, 1.2), (x0 - 2, top, x1 - x0 + 4, depth))
                pygame.draw.rect(surface, shade(colour, 0.68), (x0, top + depth, x1 - x0, max(1, depth // 3)))
            else:
                pygame.draw.rect(surface, shade(colour, 1.15), (x0, top, x1 - x0, max(2, round(f * 0.1))))
            if b.style == "deco":
                # stone piers running up the front
                for px in np.linspace(x0 + 3, x1 - 5, max(2, round((x1 - x0) / (f * 1.25)) + 1)):
                    pygame.draw.rect(surface, shade(colour, 1.1), (round(px), top + 2, 2, bottom - top - 2))
            elif b.style == "stone" and front:
                for y in range(round(top + f * 1.0), STREET_Y - SHOP_FLOOR, f * 2):
                    pygame.draw.rect(surface, shade(colour, 1.1), (x0, y, x1 - x0, 2))

        if front:
            self.drawShopFront(surface, b, colour)
        self.drawRoof(surface, b, sections[-1], f, layerIndex)

    # Rows of windows, from just under the roof down to the street (or the shops)
    def drawWindows(self, surface, b, x0, x1, top, bottom, f, layerIndex, kind, front):
        rng = self.rng
        style = STYLES[b.style]
        ww, wh, pitch = (round(style["win"][0] * f), round(style["win"][1] * f), style["win"][2] * f)
        ww, wh = max(2, ww), max(3, wh)
        margin = f * 0.4
        cols = int((x1 - x0 - 2 * margin + (pitch - ww)) // pitch)
        if cols < 1:
            return
        span = cols * pitch - (pitch - ww)
        left = x0 + (x1 - x0 - span) / 2
        floorTop = top + f * 0.42
        lowest = (STREET_Y - SHOP_FLOOR) if front else bottom - f * 0.15
        stair = rng.integers(cols) if kind == HOME and cols > 3 and rng.random() < 0.3 else None
        floor = 0
        while floorTop + f <= lowest + 1:
            y = round(floorTop + (f - wh) * 0.4)
            group = (id(b), floor) if kind == OFFICE else None
            if group:
                self.officeFloor(group)
            for c in range(cols):
                x = round(left + c * pitch)
                windowKind = STAIR if c == stair else kind
                self.addWindow(surface, pygame.Rect(x, y, ww, wh), windowKind, layerIndex, style["sash"], group)
                if style["sash"] and layerIndex > 0:
                    pygame.draw.rect(surface, shade(b.colour, 1.25), (x - 1, y + wh, ww + 2, 2))     # the sill
            floorTop += f
            floor += 1

    # A tower of glass: the whole front is windows, floor by floor, between thin metal frames
    def drawCurtainWall(self, surface, b, x0, x1, top, bottom, f, layerIndex, front):
        style = STYLES[b.style]
        pitch = style["win"][2] * f
        cols = max(1, int((x1 - x0 - 4) // pitch))
        pitch = (x1 - x0 - 4) / cols
        floorTop = top + f * 0.3
        lowest = (STREET_Y - SHOP_FLOOR) if front else bottom
        floor = 0
        while floorTop + f <= lowest + 1:
            group = (id(b), floor)
            self.officeFloor(group)
            for c in range(cols):
                rect = pygame.Rect(round(x0 + 2 + c * pitch) + 1, round(floorTop) + 1,
                                   max(1, round(pitch) - 2), max(2, round(f * style["win"][1])))
                self.addWindow(surface, rect, OFFICE, layerIndex, False, group, glass=True, colour=b.colour)
            floorTop += f
            floor += 1

    def officeFloor(self, group):
        if not hasattr(self, "floors"):
            self.floors = {}
        if group not in self.floors:
            rng = self.rng
            self.floors[group] = dict(start=rng.uniform(1140, 1250), end=rng.uniform(290, 500),
                                      weekend=rng.random() < 0.15, night=rng.random() < 0.1,
                                      threshold=rng.uniform(0.15, 0.6))

    def addWindow(self, surface, rect, kind, layerIndex, sash, group=None, glass=False, colour=None):
        rng = self.rng
        variant = int(rng.integers(6))
        key = (rect.width, rect.height, kind, variant, sash and rect.width >= 7, glass, layerIndex,
               None if colour is None else tuple(int(c) // 24 for c in colour))
        if key not in self.spriteCache:
            self.spriteCache[key] = self.windowSprites(rect.width, rect.height, kind, variant, sash and rect.width >= 7,
                                                       glass, layerIndex, colour)
        unlit, lit, refl, glow = self.spriteCache[key]
        surface.blit(unlit, rect)
        self.currentRefl.blit(refl, rect)
        window = Window(rect, lit, kind, layerIndex, rng, group)
        window.glow = glow
        window.glowRect = rect.inflate(glow.get_width() - rect.width, glow.get_height() - rect.height)
        if group is not None:
            window.threshold = self.floors[group]["threshold"] + rng.uniform(0, 0.25)
        self.windows.append(window)

    # A window by day (dark glass with the sky in it, perhaps curtains) and lit from inside
    def windowSprites(self, w, h, kind, variant, sash, glass, layerIndex, colour):
        rng = np.random.default_rng(hash((w, h, kind, variant)) & 0xFFFFFF)
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        v = yy / max(1, h - 1)
        u = xx / max(1, w - 1)

        # how much of the sky each pixel of the glass reflects: more at the top, with a streak
        streak = np.exp(-((u + v * 0.6 - 0.5 - 0.3 * (variant - 3) / 3) / 0.12) ** 2)
        reflect = (0.5 if glass else 0.3) * (0.55 + 0.45 * (1 - v)) + 0.2 * streak
        if glass:
            base = np.array(colour, np.float32) * 0.55 + 6
            unlit = base * (1.1 - 0.3 * v)[..., None] * rng.uniform(0.9, 1.1)
        else:
            base = np.array((30, 34, 42), np.float32) * rng.uniform(0.8, 1.25)
            unlit = base * (1.2 - 0.4 * v)[..., None]
            if kind in (HOME, STAIR) and variant < 2:
                curtain = np.array((150, 122, 96) if variant == 0 else (120, 110, 120), np.float32) * 0.62
                side = (u < 0.24) | (u > 0.76)
                unlit = np.where(side[..., None], curtain * (0.9 + 0.1 * np.sin(xx * 2.2))[..., None], unlit)
                reflect = np.where(side, reflect * 0.4, reflect)

        if kind == OFFICE:
            light = np.array([(236, 242, 252), (250, 244, 226), (226, 236, 255), (244, 246, 240), (255, 238, 210), (232, 240, 250)][variant], np.float32)
            lit = light * (1.0 - 0.18 * v)[..., None]
            if variant in (1, 4) and h >= 6:            # blinds part way down
                blind = v < 0.25 + 0.1 * variant / 4
                lit = np.where(blind[..., None], lit * (0.78 + 0.1 * (yy % 2))[..., None], lit)
            if h >= 8:                                  # desks and people, dark against the light
                lit *= (1 - 0.35 * ((v > 0.7) & (np.sin(xx * 0.9 + variant) > 0.2)))[..., None]
        elif kind in (SHOP, SIGN):
            lit = np.array((255, 232, 192), np.float32) * (1.05 - 0.25 * v)[..., None]
            if w > 20:
                # what is in the window: shelves, rails of clothes, things on show
                for _ in range(max(2, w // 18)):
                    cx, half = rng.uniform(0, w), rng.uniform(3, 9)
                    height = rng.uniform(0.3, 0.75)
                    tint = np.array(rng.uniform(0.35, 0.8, 3), np.float32)
                    item = (np.abs(xx - cx) < half) & (v > 1 - height)
                    lit = np.where(item[..., None], lit * tint, lit)
                for shelf in rng.uniform(0.3, 0.7, 2):
                    lit = np.where((np.abs(v - shelf) < 0.03)[..., None], lit * 0.55, lit)
                lit = np.where((v > 0.88)[..., None], lit * 0.45, lit)
            unlit = np.array((34, 38, 44), np.float32) * (1.2 - 0.3 * v)[..., None]
            reflect = 0.34 * (0.6 + 0.4 * (1 - v)) + 0.25 * np.exp(-((u * 0.4 + v - 0.6) / 0.1) ** 2)
        else:
            warm = [(255, 196, 118), (255, 214, 152), (250, 178, 104), (255, 226, 176), (255, 204, 140), (246, 190, 128)][variant]
            lit = np.array(warm, np.float32) * (1.08 - 0.3 * v)[..., None]
            if variant < 2:                              # curtains drawn, glowing
                side = (u < 0.24) | (u > 0.76)
                lit = np.where(side[..., None], lit * np.array((0.82, 0.6, 0.42), np.float32) * (0.9 + 0.1 * np.sin(xx * 2.2))[..., None], lit)
            elif variant == 3 and w >= 6:               # a lampshade
                lit += (60 * np.exp(-(((u - 0.7) / 0.18) ** 2 + ((v - 0.55) / 0.2) ** 2)))[..., None]

        if sash:
            frame = np.zeros((h, w), bool)
            frame[:, w // 2] = True
            frame[round(h * 0.45), :] = True
            unlit = np.where(frame[..., None], np.array((150, 146, 138), np.float32), unlit)
            lit = np.where(frame[..., None], np.array((70, 52, 36), np.float32), lit)
            reflect = np.where(frame, 0, reflect)

        # set back in the wall: the lintel's shadow along the top, and down one side
        unlit = np.array(unlit, np.float32)
        lit = np.array(lit, np.float32)
        reflect = np.array(np.broadcast_to(reflect, (h, w)), np.float32)
        depth = 1 if h < 14 else 2
        unlit[:depth] *= 0.4
        unlit[:, :1] *= 0.7
        lit[:depth] *= 0.55
        reflect[:depth] = 0

        if layerIndex == 0:                             # far away, through the haze
            lit = lit * 0.78
        elif layerIndex == 1:
            lit = lit * 0.9
        litImage = toSurface(lit).convert()
        grey = np.repeat(np.clip(reflect * 255, 0, 255)[..., None], 3, axis=2)
        g = max(2, round(min(w, h) * (0.9 if kind == SHOP else 0.6)))
        strength = {SHOP: 0.42, OFFICE: 0.2, HOME: 0.3, STAIR: 0.3}.get(kind, 0.3) * (0.7 if layerIndex == 0 else 1.0)
        return toSurface(unlit).convert(), litImage, toSurface(grey).convert(), windowGlow(litImage, g, strength)

    def drawShopFront(self, surface, b, colour):
        rng = self.rng
        x0, x1 = b.x0, b.x1
        y0 = STREET_Y - SHOP_FLOOR
        if rng.random() < 0.25:
            # a grand doorway for flats or offices
            pygame.draw.rect(surface, shade(colour, 0.9), (x0, y0, x1 - x0, SHOP_FLOOR))
            dx = round((x0 + x1) / 2 - 16)
            pygame.draw.rect(surface, shade(colour, 1.2), (dx - 6, y0 + 8, 44, SHOP_FLOOR - 8))
            self.addWindow(surface, pygame.Rect(dx, y0 + 14, 32, SHOP_FLOOR - 16), STAIR, 2, True)
            return

        pygame.draw.rect(surface, (38, 34, 32), (x0, y0, x1 - x0, SHOP_FLOOR))
        sign = SIGN_COLOURS[rng.integers(len(SIGN_COLOURS))]
        signRect = pygame.Rect(x0 + 6, y0 + 3, x1 - x0 - 12, 13)
        pygame.draw.rect(surface, sign, signRect)
        # letters on the sign, too small to read
        textW = rng.uniform(0.3, 0.6) * signRect.width
        start = signRect.centerx - textW / 2
        letters = []
        x = start
        while x < start + textW:
            lw = rng.integers(3, 6)
            letters.append(pygame.Rect(round(x), signRect.y + 4, lw, 5))
            x += lw + 2
        for r in letters:
            pygame.draw.rect(surface, (236, 226, 200), r)
        signWindow = Window(signRect, None, SIGN, 2, rng)
        lit = pygame.Surface(signRect.size).convert()
        lit.fill(shade(sign, 1.6 if max(sign) < 120 else 1.25))
        for r in letters:
            pygame.draw.rect(lit, (255, 250, 236), r.move(-signRect.x, -signRect.y))
        signWindow.lit = lit
        signWindow.glow = windowGlow(lit, 12, 0.55)
        signWindow.glowRect = signRect.inflate(24, 24)
        self.windows.append(signWindow)

        top = y0 + 18
        if rng.random() < 0.55:
            # a striped awning over the window
            awning = AWNING_COLOURS[rng.integers(len(AWNING_COLOURS))]
            for i, x in enumerate(range(x0 + 4, x1 - 4, 10)):
                pygame.draw.rect(surface, awning if i % 2 == 0 else (226, 220, 206), (x, top, min(10, x1 - 4 - x), 11))
            for x in range(x0 + 4, x1 - 4, 10):
                pygame.draw.circle(surface, shade(awning, 0.8), (x + 5, top + 11), 4)
            top += 17
        door = 26
        doorX = x0 + 10 if rng.random() < 0.5 else x1 - 10 - door
        pygame.draw.rect(surface, (30, 26, 24), (doorX, top + 2, door, STREET_Y - top - 2))
        glassLeft = x0 + 10 + (door + 6 if doorX == x0 + 10 else 0)
        glassRight = x1 - 10 - (door + 6 if doorX != x0 + 10 else 0)
        if glassRight - glassLeft > 12:
            rect = pygame.Rect(glassLeft, top + 3, glassRight - glassLeft, STREET_Y - 8 - top - 3)
            self.addWindow(surface, rect, SHOP, 2, False)
            pygame.draw.rect(surface, (60, 54, 50), (glassLeft - 2, STREET_Y - 8, rect.width + 4, 8))
        door = Window(pygame.Rect(doorX + 3, top + 5, door - 6, STREET_Y - top - 7), None, SHOP, 2, rng)
        door.a, door.b = signWindow.a, signWindow.b
        dw, dh = door.rect.size
        v = np.linspace(0, 1, dh, dtype=np.float32)[:, None, None]
        rgb = np.array((246, 214, 160), np.float32) * (1.0 - 0.3 * v) * np.ones((dh, dw, 1), np.float32)
        rgb[:, :2] = rgb[:, -2:] = rgb[:2] = (44, 38, 34)                       # its frame...
        rgb[round(dh * 0.55):round(dh * 0.55) + 2] = (90, 80, 70)               # ...and its handle bar
        rgb[-4:] *= 0.5
        door.lit = toSurface(rgb).convert()
        door.glow = windowGlow(door.lit, 10, 0.35)
        door.glowRect = door.rect.inflate(20, 20)
        self.windows.append(door)

    # Water towers, plant rooms, masts and spires
    def drawRoof(self, surface, b, section, f, layerIndex):
        rng = self.rng
        x0, x1, top = section
        w = x1 - x0
        colour = shade(b.colour, 0.8)
        tall = top < 430

        if b.style in ("brick", "stone") and layerIndex > 0 and rng.random() < 0.35 and w > f * 1.6:
            # a wooden water tank on legs
            tw, th = round(f * 0.75), round(f * 0.7)
            tx = round(rng.uniform(x0 + 6, x1 - 6 - tw))
            legs = round(f * 0.35)
            for lx in (tx + 2, tx + tw // 2, tx + tw - 3):
                pygame.draw.line(surface, (54, 46, 40), (lx, top), (lx, top - legs), 2)
            pygame.draw.line(surface, (54, 46, 40), (tx + 2, top - legs // 2), (tx + tw - 3, top - legs // 2), 1)
            body = pygame.Rect(tx, top - legs - th, tw, th)
            pygame.draw.rect(surface, (98, 74, 56), body)
            for hy in (body.y + th // 3, body.y + 2 * th // 3):
                pygame.draw.line(surface, (66, 54, 44), (tx, hy), (tx + tw - 1, hy), 1)
            aaPolygon(surface, (76, 60, 48), [(tx - 2, body.y), (tx + tw / 2, body.y - th * 0.4), (tx + tw + 1, body.y)])
        elif b.style in ("concrete", "glass", "dark") or rng.random() < 0.4:
            # plant rooms and air conditioners
            for _ in range(rng.integers(1, 4)):
                bw = round(rng.uniform(0.15, 0.45) * w)
                bh = round(rng.uniform(0.15, 0.4) * f) + 3
                bx = round(rng.uniform(x0 + 2, max(x0 + 3, x1 - 2 - bw)))
                pygame.draw.rect(surface, shade(colour, rng.uniform(0.8, 1.1)), (bx, top - bh, bw, bh))
                if layerIndex == 2 and len(self.vents) < 3 and rng.random() < 0.6 and top > 420:
                    vx = bx + bw // 2
                    pygame.draw.rect(surface, (70, 70, 74), (vx - 3, top - bh - 12, 6, 12))
                    self.vents.append((vx, top - bh - 12))

        if b.style == "deco" and tall:
            # a spire
            sw = w * 0.5
            mid = (x0 + x1) / 2
            spireTop = top - f * rng.uniform(2.5, 4)
            aaPolygon(surface, shade(b.colour, 1.05), [(mid - sw / 2, top), (mid, spireTop), (mid + sw / 2, top)])
            aaPolygon(surface, shade(b.colour, 0.75), [(mid, top), (mid, spireTop), (mid + sw / 2, top)])
            self.mast(surface, mid, spireTop, f * 1.2)
        elif tall and rng.random() < 0.7:
            self.mast(surface, rng.uniform(x0 + w * 0.3, x1 - w * 0.3), top - (4 if b.style == "glass" else 0), f * rng.uniform(0.8, 2.2))

    def mast(self, surface, x, top, height):
        x = round(x)
        tip = round(top - height)
        pygame.draw.line(surface, (60, 62, 66), (x, round(top)), (x, tip), 2)
        pygame.draw.line(surface, (60, 62, 66), (x - 3, round(top - height * 0.4)), (x + 3, round(top - height * 0.4)), 1)
        self.beacons.append((x, tip))

    # Light at the top, darker at the bottom, rough, and all a little different: bricks and
    # stone blocks and concrete panels, with rain streaks down them
    def texture(self, surface, buildings, layerIndex, row, windows):
        rng = self.rng
        f = row["floor"]
        topAt = np.full(W, STREET_Y, np.float32)
        for b in buildings:
            a, z = max(0, b.x0), min(W, b.x1)
            if a < z:
                topAt[a:z] = np.minimum(topAt[a:z], b.top)
        y = np.arange(H, dtype=np.float32)[None, :]
        top = topAt[:, None]
        fall = np.clip((y - top) / np.maximum(1, STREET_Y - top), 0, 1)
        factor = 1.06 - 0.14 * fall
        factor = factor * (1 - 0.3 * np.exp(-np.maximum(0, STREET_Y - y) / 26))
        xx, yy = np.mgrid[0:W, 0:H].astype(np.float32)
        factor = factor * (1 + 0.03 * waves(xx, yy, 6, 40, rng) + rng.normal(0, 0.02, (W, H)).astype(np.float32))

        # what each wall is made of (not the windows, nor the shops)
        material = np.zeros((W, H), np.int8)
        for x0, t, x1, bottom, style in self.facades:
            a, z = max(0, x0), min(W, x1)
            if a < z:
                material[a:z, max(0, t):bottom] = MATERIALS[style]
        for window in windows:
            r = window.rect.clip(pygame.Rect(0, 0, W, H))
            material[r.x:r.right, r.y:r.bottom] = 0
        if layerIndex == 2:
            material[:, STREET_Y - SHOP_FLOOR:] = 0
        X = np.arange(W)[:, None]
        Y = np.arange(H)[None, :]
        table = rng.random(4096).astype(np.float32) - 0.5
        detail = np.ones((W, H), np.float32)
        if layerIndex > 0:
            c = 3 if layerIndex == 2 else 2                 # brick courses
            course = Y // c
            brick = (X + (course % 2) * c) // (2 * c + 1)
            bricks = (1 + 0.13 * table[(course * 977 + brick * 131) % 4096]) * np.where(Y % c == 0, 0.9, 1.0)
            detail = np.where(material == 1, bricks, detail)
            bh, bw = max(4, round(f / 3)), max(8, round(f * 0.9))     # stone blocks
            course = Y // bh
            shift = (course % 2) * (bw // 2)
            block = (X + shift) // bw
            joints = (Y % bh == 0) | ((X + shift) % bw == 0)
            blocks = (1 + 0.06 * table[(course * 733 + block * 197) % 4096]) * np.where(joints, 0.93, 1.0)
            detail = np.where(material == 2, blocks, detail)
            panels = np.where((Y % f == 0) | (X % max(8, round(f * 1.6)) == 0), 0.9, 1.0)    # concrete panels
            detail = np.where(material == 3, panels * (1 + 0.05 * waves(xx, yy, 5, 25, rng)), detail)
        # rain streaks, running down from the sills and the roof
        columns = np.convolve(rng.normal(0, 1, W + 8), np.ones(5) / 5, "same")[4:W + 4].astype(np.float32)
        streaks = np.clip(columns, 0, None)[:, None] * (0.55 + 0.45 * np.sin(Y / 37.0 + rng.uniform(0, 6.3, W)[:, None]))
        detail *= np.where(material > 0, 1 - 0.09 * streaks, 1.0)
        factor *= detail

        pixels = pygame.surfarray.pixels3d(surface)
        pixels[:] = np.clip(pixels * factor[..., None], 0, 255).astype(np.uint8)
        del pixels

    ##--------------------------------------------------------------
    ## The street
    ##--------------------------------------------------------------

    # The pavement and the road, at the foot of the front row
    def drawStreet(self, surface):
        rng = self.rng
        rows = H - STREET_Y
        yy, xx = np.mgrid[STREET_Y:H, 0:W].astype(np.float32)
        noise = rng.normal(0, 1, (rows, W)).astype(np.float32)
        rough = waves(xx, yy, 6, 30, rng)

        # paving slabs
        pave = np.array((150, 147, 140), np.float32) * (1 + 0.04 * rough + 0.03 * noise)[..., None]
        joint = ((xx + (yy > STREET_Y + 20) * 28) % 56 < 1.5) | (np.abs(yy - STREET_Y - 20) < 0.8)
        pave *= np.where(joint, 0.8, 1.0)[..., None]
        pave *= (1 - 0.25 * np.exp(-(yy - STREET_Y) / 6))[..., None]        # in the shade of the buildings
        kerb = (yy >= KERB_Y - 6) & (yy < KERB_Y)
        pave = np.where(kerb[..., None], np.array((176, 174, 168), np.float32) * (1 + 0.03 * noise)[..., None], pave)

        # the road, a little paler where the tyres go, with a dashed line down the middle
        road = np.array((62, 63, 67), np.float32) * (1 + 0.05 * rough + 0.07 * noise)[..., None]
        road *= (1.08 - 0.12 * (yy - KERB_Y) / (H - KERB_Y))[..., None]
        for lane in (FAR_LANE_Y - 8, NEAR_LANE_Y - 10):
            road *= (1 + 0.06 * np.exp(-((yy - lane) / 14) ** 2))[..., None]
        dash = (np.abs(yy - MARKING_Y) < 2.2) & ((xx % 96) < 48)
        road = np.where(dash[..., None], np.array((206, 204, 192), np.float32) * (0.9 + 0.05 * noise)[..., None], road)
        gutter = (yy >= KERB_Y) & (yy < KERB_Y + 4)
        road = np.where(gutter[..., None], road * 0.55, road)
        for mx in rng.uniform(100, W - 100, 2):
            cover = ((xx - mx) / 22) ** 2 + ((yy - (FAR_LANE_Y + NEAR_LANE_Y) / 2 - 14) / 5) ** 2 < 1
            road = np.where(cover[..., None], road * 0.7, road)

        rgb = np.where((yy < KERB_Y)[..., None], pave, road)
        street = toSurface(rgb)
        surface.blit(street, (0, STREET_Y))
        return surface

    # Street lamps and trees along the pavement, in front of the buildings
    def drawStreetThings(self):
        rng = self.rng
        surface = pygame.Surface((W, H), pygame.SRCALPHA)
        surface.fill((0, 0, 0, 0))
        month = datetime.date.today().month

        spacing = 330
        start = rng.uniform(60, spacing)
        lampXs = list(np.arange(start, W + 40, spacing))
        for i, x in enumerate(lampXs):
            x = round(x + rng.uniform(-20, 20))
            treeX = x + spacing / 2 + rng.uniform(-40, 40)
            if rng.random() < 0.7 and treeX < W + 40:
                self.drawTree(surface, treeX, month)
        for x in lampXs:
            x = round(x)
            self.drawLamp(surface, x)

        # a litter bin or two, and a post box
        for _ in range(2):
            bx = round(rng.uniform(40, W - 40))
            pygame.draw.rect(surface, (40, 44, 42), (bx, KERB_Y - 30, 14, 22), border_radius=3)
        px = round(rng.uniform(40, W - 40))
        pygame.draw.rect(surface, (176, 24, 22), (px, KERB_Y - 40, 14, 34), border_top_left_radius=7, border_top_right_radius=7)
        pygame.draw.rect(surface, (20, 18, 18), (px + 3, KERB_Y - 30, 8, 2))
        return dict(surface=surface, haze=0.0)

    def drawLamp(self, surface, x):
        base = KERB_Y - 4
        top = base - 150
        pole = (38, 42, 40)
        pygame.draw.rect(surface, pole, (x - 3, top, 5, base - top))
        pygame.draw.rect(surface, pole, (x - 5, base - 14, 9, 14), border_radius=2)
        pygame.draw.line(surface, pole, (x, top + 2), (x + 30, top - 4), 3)
        aaPolygon(surface, (52, 56, 54), [(x + 20, top - 8), (x + 46, top - 6), (x + 42, top), (x + 24, top - 1)])
        pygame.draw.rect(surface, (226, 222, 206), (x + 25, top - 1, 16, 2))
        self.lamps.append((x + 33, top + 1, float(self.rng.uniform(0.32, 0.5))))

    def drawTree(self, surface, x, month):
        rng = self.rng
        S = 3
        tw, th = 120, 170
        tree = pygame.Surface((tw * S, th * S), pygame.SRCALPHA)
        tree.fill((0, 0, 0, 0))
        trunk = (66, 54, 46)
        cx = tw * S // 2
        ground = th * S - 4 * S
        pygame.draw.line(tree, trunk, (cx, ground), (cx, ground - 80 * S), 5 * S)
        pygame.draw.rect(tree, (70, 66, 60), (cx - 12 * S, ground - 2 * S, 24 * S, 3 * S))     # the grille round its foot

        def branch(x0, y0, angle, length, width, depth):
            x1 = x0 + math.sin(angle) * length
            y1 = y0 - math.cos(angle) * length
            pygame.draw.line(tree, trunk, (x0, y0), (x1, y1), max(1, round(width)))
            if depth:
                for turn in (-0.45, 0.4):
                    branch(x1, y1, angle + turn + rng.uniform(-0.2, 0.2), length * rng.uniform(0.62, 0.78), width * 0.65, depth - 1)

        if month in (12, 1, 2):
            branch(cx, ground - 60 * S, 0, 30 * S, 4 * S, 5)
        else:
            branch(cx, ground - 60 * S, 0, 24 * S, 4 * S, 3)
            greens = {3: [(120, 150, 70), (150, 176, 90)], 4: [(96, 150, 60), (130, 176, 80)],
                      9: [(96, 120, 50), (150, 140, 50), (120, 130, 56)],
                      10: [(170, 120, 40), (150, 90, 36), (190, 150, 60)], 11: [(170, 90, 34), (140, 70, 30), (190, 120, 50)]}
            leaves = np.array(greens.get(month, [(62, 110, 48), (80, 128, 56), (52, 96, 44)]), np.float32)
            sparse = 0.08 if month == 11 else (0.04 if month == 10 else 0.0)
            self.addLeaves(tree, cx, ground - 110 * S, 44 * S, 38 * S, leaves, sparse, S)
        tree = pygame.transform.smoothscale(tree, (tw, th))
        surface.blit(tree, (round(x - tw / 2), KERB_Y - th + 4))

    # A crown of leaves: clumps, ragged at their edges, lit from above and to the left, with
    # the branches showing through the gaps
    def addLeaves(self, tree, cx, cy, rx, ry, leaves, sparse, S):
        rng = self.rng
        w, h = tree.get_size()
        xx, yy = np.mgrid[0:w, 0:h].astype(np.float32)
        density = np.zeros((w, h), np.float32)
        for _ in range(22):
            a = rng.uniform(0, 2 * math.pi)
            r = rng.uniform(0, 1) ** 0.6
            bx, by = cx + math.cos(a) * r * rx, cy + math.sin(a) * r * ry
            size = rng.uniform(12, 20) * S
            density += np.exp(-((xx - bx) ** 2 + (yy - by) ** 2) / (size * size))
        clumps = fractal(h, w, 9 * S, 3, rng).T - 0.5
        fine = fractal(h, w, 2.5 * S, 2, rng).T - 0.5
        body = density + 0.7 * clumps
        alpha = smoothstep(0.42 + sparse, 0.52 + sparse, body + 0.45 * fine)
        gx, gy = np.gradient(body)
        length = np.sqrt(gx * gx + gy * gy) + 0.02
        facing = (gx * 0.55 + gy * 0.8) / length            # the outside faces the light where the crown thins towards it
        light = np.clip(0.5 + 0.35 * facing - 0.3 * np.clip(body - 1.0, 0, 1) + 0.5 * fine, 0.1, 1.1)
        mix = fractal(h, w, 14 * S, 2, rng).T
        index = np.clip((mix * len(leaves)).astype(int), 0, len(leaves) - 1)
        rgb = leaves[index] * (0.45 + 0.75 * light)[..., None]

        pixels = pygame.surfarray.pixels3d(tree)
        alphas = pygame.surfarray.pixels_alpha(tree)
        under = alphas / 255.0
        total = alpha + under * (1 - alpha)
        pixels[:] = np.clip((rgb * alpha[..., None] + pixels * (under * (1 - alpha))[..., None]) /
                            np.maximum(total, 1e-3)[..., None], 0, 255).astype(np.uint8)
        alphas[:] = np.clip(total * 255, 0, 255).astype(np.uint8)
        del pixels, alphas

    # Puts the rows together, once, as one picture (albedo) with each row already darkened by
    # the haze in front of it, and a grey picture of how much haze is in front of each pixel
    # (hazeMask), so that lighting the city takes one multiply and one add, however many rows
    def mergeRows(self):
        size = (W, H - self.cityTop)
        self.albedo = pygame.Surface(size, pygame.SRCALPHA).convert_alpha()
        self.albedo.fill((0, 0, 0, 0))
        mask = pygame.Surface(size, pygame.SRCALPHA).convert_alpha()
        mask.fill((0, 0, 0, 0))
        reflect = pygame.Surface(size).convert()
        reflect.fill((0, 0, 0))
        for layer in self.layers:
            x, y = layer["offset"]
            where = (x, y - self.cityTop)
            image = layer["surface"].copy()
            clear = round(255 * (1 - layer["haze"]))
            image.fill((clear, clear, clear), special_flags=pygame.BLEND_RGB_MULT)
            self.albedo.blit(image, where)
            grey = round(255 * layer["haze"])
            image.fill((0, 0, 0), special_flags=pygame.BLEND_RGB_MULT)
            reflect.blit(image, where)              # what this row hides, reflects nothing...
            image.fill((grey, grey, grey), special_flags=pygame.BLEND_RGB_ADD)
            mask.blit(image, where)
            if layer.get("refl") is not None:       # ...but its own windows do
                panes = layer["refl"].copy()
                panes.fill((clear, clear, clear), special_flags=pygame.BLEND_RGB_MULT)
                reflect.blit(panes, where, special_flags=pygame.BLEND_RGB_ADD)
        self.hazeMask = mask.convert()
        self.reflectMask = reflect
        self.albedo.blit(self.vignette, (0, -self.cityTop), special_flags=pygame.BLEND_RGB_MULT)

    # The sides of the buildings that can be seen, each as a small picture (black where it
    # cannot be seen), for adding the sun to when it shines on them
    def extractSides(self):
        self.sides = []
        albedo = pygame.surfarray.pixels3d(self.albedo)
        codes = {}
        for side in self.sideFaces:
            index = side["layer"]
            if index not in codes:
                ids = pygame.surfarray.pixels3d(self.layers[index]["ids"])
                codes[index] = ids[..., 0].astype(np.int32) + ids[..., 1].astype(np.int32) * 256
                del ids
            x0, y0, x1, y1 = side["box"]
            x0, x1 = max(0, x0), min(W, x1)
            y0, y1 = max(self.cityTop, y0), min(H, y1)
            if x1 - x0 < 1 or y1 - y0 < 1:
                continue
            seen = (codes[index][x0:x1, y0:y1] == side["code"]) & ~self.nearer[index][x0:x1, y0:y1]
            if seen.sum() < 4:
                continue
            rgb = albedo[x0:x1, y0 - self.cityTop:y1 - self.cityTop] * seen[..., None]
            image = pygame.surfarray.make_surface(rgb.astype(np.uint8)).convert()
            self.sides.append((image, (x0, y0 - self.cityTop), side["normal"]))
        del albedo

    # Which windows' light overlaps which, so that turning one off can put back the others'
    def findNeighbours(self):
        rects = [w.glowRect for w in self.windows]
        for window in self.windows:
            window.near = [self.windows[i] for i in window.glowRect.collidelistall(rects) if self.windows[i] is not window]

    # Windows hidden behind something nearer can never be seen lit
    def hideCoveredWindows(self):
        covers = []
        for layer in self.layers:
            alpha = np.zeros((W, H), np.uint8)
            x, y = layer["offset"]
            a = pygame.surfarray.array_alpha(layer["surface"])
            alpha[x:x + a.shape[0], y:y + a.shape[1]] = a
            covers.append(alpha > 40)
        nearer = [None] * len(covers)
        acc = np.zeros((W, H), bool)
        for i in range(len(covers) - 1, -1, -1):
            nearer[i] = acc.copy()
            acc |= covers[i]
        self.nearer = nearer
        kept = []
        for window in self.windows:
            rect = window.rect
            r = rect.clip(pygame.Rect(0, 0, W, H))
            if not (r.width and r.height):
                continue
            covered = np.zeros(rect.size, bool)
            covered[r.x - rect.x:r.right - rect.x, r.y - rect.y:r.bottom - rect.y] = nearer[window.layer][r.x:r.right, r.y:r.bottom]
            amount = covered.mean()
            if amount > 0.6:
                continue
            if amount > 0:
                # partly behind a lamp post or a tree: its light only where it can be seen
                lit = window.lit.convert_alpha()
                alpha = pygame.surfarray.pixels_alpha(lit)
                alpha[covered] = 0
                del alpha
                window.lit = lit
            kept.append(window)
        self.windows = kept
        self.beacons = [(x, y) for x, y in self.beacons if 0 <= x < W and 0 <= y < H and not covers[2][x, y] and not covers[1][x, y]]
        self.vents = [(x, y) for x, y in self.vents if 0 <= x < W]

    ##--------------------------------------------------------------
    ## The sky's things, made once
    ##--------------------------------------------------------------

    def makeStars(self):
        rng = self.rng
        height = HORIZON_Y
        rgb = np.zeros((height, W, 3), np.float32)
        count = 1100
        xs = rng.integers(0, W, count)
        ys = (rng.random(count) ** 1.25 * (height - 20)).astype(int)
        level = 30 + 225 * rng.random(count) ** 7
        level *= 1 - 0.75 * np.clip(ys / height, 0, 1) ** 2        # fewer near the glow of the city
        tints = np.array([(255, 255, 255), (210, 222, 255), (255, 236, 210), (255, 250, 236)], np.float32)
        colour = tints[rng.integers(len(tints), size=count)] / 255
        for x, y, l, c in zip(xs, ys, level, colour):
            rgb[y, x] += l * c
            if l > 150:
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    if 0 <= x + dx < W and 0 <= y + dy < height:
                        rgb[y + dy, x + dx] += l * c * 0.3
        stars = toSurface(rgb).convert()
        bright = np.argsort(-level)[:45]
        sprites = [glowSprite(4, (255, 255, 255), core=0.35, power=k / 5) for k in range(6)]
        twinkles = [(int(xs[i]), int(ys[i]), rng.uniform(0, 6.3), rng.uniform(1.5, 4)) for i in bright]
        return stars, (twinkles, sprites)

    # A faint grain, added and taken away again, so that the smooth sky does not show bands
    def makeDither(self):
        rng = self.rng
        plus = toSurface(rng.integers(0, 3, (H, W, 1)).repeat(3, axis=2).astype(np.float32)).convert()
        minus = toSurface(rng.integers(0, 3, (H, W, 1)).repeat(3, axis=2).astype(np.float32)).convert()
        return plus, minus

    def makeSun(self):
        size = 220
        yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
        r = np.hypot(xx - size / 2 + 0.5, yy - size / 2 + 0.5)
        disc = np.clip(24.5 - r, 0, 1)
        level = disc + 0.5 * np.exp(-((r - 20) / 14) ** 2) * (r > 20) + 0.25 * np.exp(-r / 40)
        return toSurface(np.full((size, size, 3), 255, np.float32) * np.clip(level, 0, 1)[..., None]).convert()

    # The moon, lit from where the sun is (dx, dy on the screen), a fraction of the way from new
    # to full (elongation, radians), with its seas, and the faint earthshine on the rest
    def makeMoon(self, elongation, dx, dy):
        R = 30
        size = 2 * R + 4
        yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
        x = (xx - size / 2 + 0.5) / R
        y = (yy - size / 2 + 0.5) / R
        r2 = x * x + y * y
        z = np.sqrt(np.clip(1 - r2, 0, 1))
        length = math.hypot(dx, dy) or 1
        sx, sy = dx / length, dy / length
        lx, ly, lz = sx * math.sin(elongation), sy * math.sin(elongation), -math.cos(elongation)
        lit = smoothstep(-0.04, 0.08, x * lx + y * ly + z * lz)
        rng = np.random.default_rng(7)
        seas = np.zeros_like(x)
        for mx, my, mr in ((-0.3, -0.25, 0.32), (0.2, -0.35, 0.25), (0.05, 0.05, 0.3), (-0.4, 0.25, 0.22), (0.35, 0.3, 0.18)):
            seas += np.exp(-(((x - mx) ** 2 + (y - my) ** 2) / mr ** 2) ** 2)
        albedo = 0.95 - 0.22 * np.clip(seas, 0, 1) + 0.04 * rng.normal(0, 1, x.shape)
        level = albedo * (0.05 + 0.95 * lit) * (0.75 + 0.25 * z)
        level *= np.clip((1 - np.sqrt(r2)) * R + 0.5, 0, 1)
        rgb = np.array((246, 242, 228), np.float32) * level[..., None]
        return toSurface(rgb).convert()         # added to the sky, so that its dark side cannot be seen by day

    # Clouds: puffy heaps and long thin streaks. Each is kept as how thick it is, which way its
    # surface faces at each pixel, and its fine detail, and is lit afresh as the light changes.
    def makeCloudShape(self, index):
        rng = self.rng
        streak = index % 3 == 2
        if streak:
            w, h = int(rng.uniform(600, 900)), int(rng.uniform(50, 90))
        else:
            w, h = int(rng.uniform(320, 620)), int(rng.uniform(140, 230))
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        density = np.zeros((h, w), np.float32)
        baseY = h * 0.8
        if streak:
            for _ in range(8):
                cx, cy = rng.uniform(0.1, 0.9) * w, rng.uniform(0.35, 0.65) * h
                density += np.exp(-(((xx - cx) / (w * rng.uniform(0.12, 0.3))) ** 2 + ((yy - cy) / (h * 0.2)) ** 2))
            density *= 0.75
            billows = fractal(h * 4, w, 40, 4, rng)[::4] - 0.5      # stretched out sideways
        else:
            for _ in range(int(rng.integers(8, 15))):
                cx = rng.uniform(0.18, 0.82) * w
                middle = 1 - abs(cx / w - 0.5) * 1.6
                r = (0.16 + 0.22 * middle * rng.uniform(0.6, 1.2)) * h
                cy = baseY - r * rng.uniform(0.3, 0.9)
                density += np.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / (r * r))
            density *= smoothstep(baseY + 6, baseY - 12, yy)          # a flat bottom
            billows = fractal(h, w, 36, 5, rng) - 0.5
        fine = fractal(h, w, 12, 3, rng) - 0.5
        body = density + 0.9 * billows
        alpha = smoothstep(0.3, 0.85, body + 0.2 * fine)
        if not streak:
            alpha *= smoothstep(baseY + 6, baseY - 4, yy)
        u, v = xx / w, yy / h                       # fading out well before the edges of its picture
        alpha *= smoothstep(0, 0.12, u) * smoothstep(0, 0.12, 1 - u) * smoothstep(0, 0.15, v) * smoothstep(0, 0.15, 1 - v)
        # which way its surface faces: the big shape, and the billows on it
        gy, gx = np.gradient(density + 0.5 * billows)
        length = np.sqrt(gx * gx + gy * gy) + 0.03
        by, bx = np.gradient(billows)
        bumps = np.clip(-by * 25, -1, 1)            # the upper sides of the billows
        height = np.clip((baseY - yy) / baseY, 0, 1) if not streak else np.full_like(yy, 0.5)
        return dict(alpha=alpha, nx=-gx / length, ny=-gy / length, bumps=bumps, height=height,
                    thick=np.clip(body - 0.6, 0, 1), fine=fine, size=(w, h), streak=streak)

    def makeLampGlow(self):
        headY = 92
        w, h = 560, headY + H - (KERB_Y - 153)
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        dx = xx - w / 2
        r = np.hypot(dx, yy - headY)
        halo = np.exp(-(r / 9) ** 2) * 1.4 + 0.3 * np.exp(-r / 28)
        down = yy - headY
        cone = np.exp(-(np.abs(dx) / (6 + 0.55 * np.maximum(down, 0))) ** 2) * 0.12 * (down > 0) * np.clip(down / 30, 0, 1)
        poolY = headY + (KERB_Y - (KERB_Y - 4 - 150 + 1)) + 6
        pool = 0.42 * np.exp(-((dx / 125) ** 2 + ((yy - poolY) / 24) ** 2))
        wall = 0.16 * np.exp(-((dx / 90) ** 2 + ((yy - poolY + 60) / 60) ** 2))
        # the damp road: the lamp's light, stretched down towards you
        below = yy - (poolY + 6)
        ripples = np.random.default_rng(int(w)).random(h).astype(np.float32)
        ripples = np.convolve(ripples, np.ones(4) / 4, "same")[:, None]      # broken up by the ripples in the wet
        wobble = 1.2 * np.sin(yy * 0.09) + 0.8 * (ripples - 0.5)
        streak = (0.2 * np.exp(-((dx + wobble) / 7) ** 2) + 0.06 * np.exp(-(dx / 28) ** 2)) * (0.45 + 0.9 * ripples) * \
            (below > 0) * np.exp(-np.maximum(below, 0) / 140) * np.clip(below / 12, 0, 1)
        level = np.clip(halo + cone + pool + wall + streak, 0, 2)
        rgb = np.array((255, 196, 128), np.float32) * level[..., None]
        return toSurface(rgb).convert(), headY

    def makeBeam(self):
        w, h = 180, 40
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        level = np.exp(-xx / 70) * (1 - xx / w) ** 2 * np.exp(-((yy - h / 2) / (2.5 + xx * 0.04)) ** 2) * 0.5
        return toSurface(np.array((255, 236, 196), np.float32) * level[..., None]).convert()

    def makePuffs(self):
        puffs = []
        for r in range(6, 40, 3):
            size = r * 2
            yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
            d = np.hypot(xx - r + 0.5, yy - r + 0.5) / r
            alpha = np.exp(-(d * 1.8) ** 2) * 255
            puffs.append(toSurface(np.full((size, size, 3), 255, np.float32), alpha))
        return puffs

    def makeContrail(self):
        w, h = 420, 7
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        spread = 1 + xx / w * 2.2
        alpha = np.exp(-((yy - h / 2) / spread) ** 2) * np.exp(-xx / 220) * 150 * np.clip(xx / 10, 0, 1)
        return toSurface(np.full((h, w, 3), 255, np.float32), alpha)

    ##--------------------------------------------------------------
    ## Cars and people
    ##--------------------------------------------------------------

    # (in its own thread)
    def makeCars(self):
        started = time.monotonic()
        rng = np.random.default_rng()
        models = self.newModels
        for _ in range(10):
            kind = str(rng.choice(["saloon", "hatch", "estate", "suv", "van", "taxi"], p=[0.22, 0.24, 0.14, 0.18, 0.11, 0.11]))
            colour = (22, 22, 24) if kind == "taxi" else vehicles.CAR_COLOURS[rng.integers(len(vehicles.CAR_COLOURS))]
            if kind == "van" and rng.random() < 0.6:
                colour = (236, 236, 232)                    # most vans are white
            models.append(self.makeVehicle(vehicles.VEHICLES[kind], colour))
        models.append(self.makeVehicle(vehicles.VEHICLES["double"], (176, 24, 28)))
        models.append(self.makeVehicle(vehicles.VEHICLES["single"], (40, 84, 150)))
        print(f"City: vehicles made in {time.monotonic() - started:.1f}s")

    # A vehicle in 3D, seen from where you stand at each of VIEW_X, facing each way, in each lane
    def makeVehicle(self, spec, colour):
        nearScale = LANE_SCALE[1]
        model = vehicles.makeModel(spec, colour, spec["length"] * nearScale)
        views = [vehicles.view(model, 960 - x, HORIZON_Y - NEAR_LANE_Y) for x in VIEW_X]
        lanes = {}
        for lane in (0, 1):
            k = LANE_SCALE[lane] / nearScale
            length = spec["length"] * LANE_SCALE[lane]
            seen = []
            for b in range(len(VIEW_X)):
                flip = LANE_DIRECTION[lane] < 0     # going left: the mirror image of one going right
                v = views[len(VIEW_X) - 1 - b] if flip else views[b]
                image, shine, inside = v["image"], v["shine"], v["inside"]
                (ax, ay), (hx, hy), (tx, ty), wheels = v["anchor"], v["head"], v["tail"], list(v["wheels"])
                w, h = image.get_size()
                if flip:
                    image = pygame.transform.flip(image, True, False)
                    shine = pygame.transform.flip(shine, True, False)
                    inside = pygame.transform.flip(inside, True, False) if inside else None
                    ax, hx, tx = w - ax, w - hx, w - tx
                    wheels = [w - x for x in wheels]
                if k != 1:
                    size = (max(1, round(w * k)), max(1, round(h * k)))
                    image = pygame.transform.smoothscale(image, size)
                    shine = pygame.transform.smoothscale(shine, size)
                    inside = pygame.transform.smoothscale(inside, size) if inside else None
                    ax, ay, hx, hy, tx, ty = (c * k for c in (ax, ay, hx, hy, tx, ty))
                    wheels = [x * k for x in wheels]
                left = ax - length / 2              # where its shadow starts, in the picture
                seen.append(dict(image=image, shine=shine, inside=inside, anchor=(ax, ay), head=(hx, hy), tail=(tx, ty),
                                 shown=image, lamplit=image,
                                 shadow=self.carShadow(round(length), [x - left for x in wheels])))
            lanes[lane] = dict(views=seen, length=length, bus=bool(spec.get("bus")))
        return lanes

    # The daylight on a vehicle, and the sky in its paint and glass
    def lightVehicle(self, model):
        if self.vehicleLight is None:
            return
        light, sky = self.vehicleLight
        for lane in model.values():
            for version in lane["views"]:
                shown = tinted(version["image"], light)
                shown.blit(tinted(version["shine"], sky), (0, 0), special_flags=pygame.BLEND_RGB_ADD)
                version["shown"] = shown
                version["lamplit"] = tinted(version["image"], (150, 116, 80))      # under a street lamp

    # A soft dark patch on the road under a vehicle, darkest under its tyres
    @staticmethod
    def carShadow(width, wheels):
        h = 12
        yy, xx = np.mgrid[0:h, 0:width].astype(np.float32)
        u = (xx - width / 2 + 0.5) / (width / 2 - 2)
        v = (yy - h / 2 + 0.5) / (h / 2)
        alpha = np.clip(1 - u ** 8 - v ** 2, 0, 1) * 110
        for x in wheels:
            alpha += 120 * np.exp(-(((xx - x) / 5) ** 2 + ((yy - h / 2) / 2) ** 2))
        return toSurface(np.zeros((h, width, 3), np.float32), np.clip(alpha, 0, 230))

    # People walking, each as eight pictures of a stride, facing right and left
    def makeWalkers(self):
        rng = self.rng
        coats = [(40, 46, 70), (150, 130, 100), (120, 30, 34), (26, 26, 28), (90, 92, 96), (40, 70, 52), (170, 150, 120), (60, 40, 70)]
        skins = [(232, 196, 166), (200, 150, 110), (150, 100, 70), (96, 64, 44), (240, 210, 186)]
        hairs = [(30, 24, 20), (80, 56, 36), (150, 120, 70), (60, 60, 60), (20, 16, 14)]
        walkers = []
        for _ in range(10):
            coat = coats[rng.integers(len(coats))]
            legs = (32, 32, 40) if rng.random() < 0.7 else (70, 60, 50)
            skin = skins[rng.integers(len(skins))]
            hair = hairs[rng.integers(len(hairs))]
            height = rng.uniform(28, 34)
            long = rng.random() < 0.4
            frames = [self.drawWalker(height, coat, legs, skin, hair, long, i / 8) for i in range(8)]
            walkers.append(dict(right=frames, left=[pygame.transform.flip(f, True, False) for f in frames],
                                height=height, shown=None))
        return walkers

    def drawWalker(self, height, coat, legs, skin, hair, long, phase):
        S = 4
        w, h = int(height * 0.7), int(height + 3)
        image = pygame.Surface((w * S, h * S), pygame.SRCALPHA)
        image.fill((0, 0, 0, 0))
        u = height * S
        cx = w * S / 2
        hip = (cx, 0.52 * u + S)
        shoulder = (cx + 0.03 * u, 0.2 * u + S)
        swing = math.sin(phase * 2 * math.pi)
        lift = math.cos(phase * 2 * math.pi)
        legLength = 0.47 * u
        for side in (-1, 1):
            a = 0.42 * swing * side
            knee = (hip[0] + math.sin(a) * legLength * 0.5, hip[1] + math.cos(a) * legLength * 0.5)
            bend = max(0, -lift * side) * 0.5
            foot = (knee[0] + math.sin(a - bend) * legLength * 0.5, knee[1] + math.cos(a - bend) * legLength * 0.5)
            colour = legs if side > 0 else shade(legs, 0.75)
            pygame.draw.line(image, colour, hip, knee, round(0.085 * u))
            pygame.draw.line(image, colour, knee, foot, round(0.075 * u))
            pygame.draw.line(image, (20, 18, 18), foot, (foot[0] + 0.07 * u, foot[1]), round(0.05 * u))
        back = shade(coat, 0.7)
        arm = 0.36 * u
        a = -0.5 * swing
        pygame.draw.line(image, back, shoulder, (shoulder[0] + math.sin(-a) * arm, shoulder[1] + math.cos(-a) * arm), round(0.075 * u))
        hem = 0.72 if long else 0.56
        pygame.draw.polygon(image, coat, [(cx - 0.08 * u, 0.2 * u + S), (cx + 0.11 * u, 0.2 * u + S),
                                          (cx + 0.1 * u, hem * u + S), (cx - 0.1 * u, hem * u + S)])
        hand = (shoulder[0] + math.sin(a) * arm, shoulder[1] + math.cos(a) * arm)
        pygame.draw.line(image, coat, shoulder, hand, round(0.08 * u))
        pygame.draw.circle(image, skin, hand, 0.035 * u)
        head = (cx + 0.04 * u, 0.1 * u + S)
        pygame.draw.circle(image, skin, head, 0.075 * u)
        pygame.draw.circle(image, hair, (head[0] - 0.02 * u, head[1] - 0.025 * u), 0.068 * u)
        return pygame.transform.smoothscale(image, (w, h))

    ##--------------------------------------------------------------
    ## The clock
    ##--------------------------------------------------------------

    def makeClockFonts(self):
        path = os.path.join(fonts.FONT_FOLDER, "Antonio-Regular.ttf")
        try:
            self.timeFont = pygame.font.Font(path, CLOCK_SIZE)
            self.dateFont = pygame.font.Font(path, DATE_SIZE)
        except (pygame.error, OSError):
            self.timeFont = pygame.font.SysFont(SANS_FONTS, CLOCK_SIZE)
            self.dateFont = pygame.font.SysFont(SANS_FONTS, DATE_SIZE)
        self.dateY = round(self.timeFont.get_ascent() * 1.02)

    def spacedWidth(self, text, spacing=6):
        return sum(self.dateFont.size(c)[0] + spacing for c in text) - spacing

    def spaced(self, text, colour, spacing=6):
        image = pygame.Surface((self.spacedWidth(text, spacing), self.dateFont.get_height()), pygame.SRCALPHA)
        image.fill((0, 0, 0, 0))
        x = 0
        for c in text:
            letter = self.dateFont.render(c, True, colour)
            image.blit(letter, (x, 0))
            x += letter.get_width() + spacing
        return image

    # The time and the date, with a soft shadow, as (picture, where), and the colon by itself
    def makeClock(self, now, night, preview=None):
        hour = now.hour if HOURS_24 else (now.hour % 12 or 12)
        hh = f"{hour:02d}" if HOURS_24 else str(hour)
        mm = f"{now.minute:02d}"
        colour = tuple(round(c * (0.86 if night else 1.0)) for c in (CLOCK_COLOUR if preview is None else PREVIEW_COLOUR))
        hhImage = self.timeFont.render(hh, True, colour)
        mmImage = self.timeFont.render(mm, True, colour)
        colon = self.timeFont.render(":", True, colour)
        gap = round(CLOCK_SIZE * 0.03)
        width = hhImage.get_width() + colon.get_width() + mmImage.get_width() + 2 * gap
        if preview is None:
            date = self.spaced(now.strftime("%A %d %B").upper().replace(" 0", " "), colour)
        else:
            date = self.spaced(f"PREVIEW - BACK TO NOW IN {preview}S", colour)

        pad = 30
        total = max(width, date.get_width())
        height = self.dateY + date.get_height()
        text = pygame.Surface((total + 2 * pad, height + 2 * pad), pygame.SRCALPHA)
        text.fill((0, 0, 0, 0))
        right = pad + total
        text.blit(hhImage, (right - width, pad))
        colonPos = (right - width + hhImage.get_width() + gap, pad)
        text.blit(mmImage, (right - mmImage.get_width(), pad))
        text.blit(date, (right - date.get_width(), pad + self.dateY))

        # the shadow: the words in black, blurred by shrinking and growing again
        shadow = text.copy()
        shadow.blit(colon, colonPos)
        shadow.fill((0, 0, 0, 255), special_flags=pygame.BLEND_RGBA_MIN)
        shadow.fill((255, 255, 255, 150 if not night else 110), special_flags=pygame.BLEND_RGBA_MULT)
        size = shadow.get_size()
        small = pygame.transform.smoothscale(shadow, (size[0] // 6, size[1] // 6))
        shadow = pygame.transform.smoothscale(small, size)
        shadow.blit(text, (-2, -3))
        where = (CLOCK_RIGHT - right, CLOCK_TOP - pad)
        return shadow, where, colon, (where[0] + colonPos[0] - 2, where[1] + colonPos[1] - 3)

    ##--------------------------------------------------------------
    ## Every so often: the sky, and the light on the city
    ##--------------------------------------------------------------

    # All at once (when the face is shown)...
    def refresh(self, now):
        for _ in self.refreshSteps(now):
            pass

    # ...or a step at a time, one each frame, so that the cars and the clouds keep moving
    # smoothly while it is done. The new sky and the new light are put up when they are ready.
    def refreshSteps(self, now):
        ts = now.timestamp()
        (sunAlt, sunAz), (moonAlt, moonAz), elongation = sunAndMoon(ts)
        colours = skyColours(sunAlt)
        dark = darknessFor(sunAlt)
        starLevel = float(smoothstep(-5, -15, sunAlt))
        cloudiness = self.cloudiness(ts)
        self.state = dict(sunAlt=sunAlt, sunAz=sunAz, sun=skyPoint(sunAlt, sunAz), dark=dark, colours=colours,
                          starLevel=starLevel * (1 - 0.5 * cloudiness), cloudiness=cloudiness, ts=ts)
        yield from self.drawSky(colours, sunAlt, skyPoint(sunAlt, sunAz), skyPoint(moonAlt, moonAz), moonAlt,
                                elongation, starLevel, dark)
        for i, cloud in enumerate(list(self.clouds)):
            cloud["image"] = self.cloudImage(cloud)
            if i % 2 == 1:
                yield
        yield from self.lightCity(colours, dark)

    # How cloudy it is: it wanders slowly between the two CITY_CLOUDINESS, over hours and days
    def cloudiness(self, ts):
        days = ts / 86400
        wander = 0.5 + 0.3 * math.sin(days * 2.1 + 1.3) + 0.2 * math.sin(days * 7.7 + 0.4)
        low, high = CLOUDINESS
        return low + (high - low) * max(0.0, min(1.0, wander))

    def drawSky(self, colours, sunAlt, sun, moon, moonAlt, elongation, starLevel, dark):
        yy, xx = np.mgrid[0:SH, 0:SW].astype(np.float32)
        xx = (xx + 0.5) * SMALL
        yy = (yy + 0.5) * SMALL
        t = np.clip(yy / HORIZON_Y, 0, 1)
        g = t ** 1.3
        rgb = colours["zenith"] * (1 - g)[..., None] + colours["horizon"] * g[..., None]

        sx, sy = sun
        dx, dy = xx - sx, yy - sy
        d = np.hypot(dx, dy * 1.15)
        near = 0.85 * np.exp(-d / 130) + 0.4 * np.exp(-d / 520)
        band = np.exp(-(dx / 1100) ** 2) * t ** 2.2 * float(smoothstep(14, 1, sunAlt) * smoothstep(-14, -3, sunAlt))
        rgb = screenBlend(rgb, colours["glow"] * (near + 0.9 * band)[..., None])
        rgb = rgb * (1 + 0.08 * np.exp(-np.abs(dx) / 700) * (1 - dark))[..., None]     # brighter on the sun's side

        # the glow of the city's lights on the haze, low down
        rgb = rgb + np.array((44, 32, 30), np.float32) * (dark * t ** 6)[..., None]
        sky = pygame.transform.smoothscale(toSurface(rgb).convert(), (W, H))
        yield
        plus, minus = self.dither
        sky.blit(plus, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
        sky.blit(minus, (0, 0), special_flags=pygame.BLEND_RGB_SUB)
        yield
        sky.blit(self.vignette, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
        yield

        if starLevel > 0.01:
            level = round(255 * starLevel)
            stars = self.stars.copy()
            stars.fill((level, level, level), special_flags=pygame.BLEND_RGB_MULT)
            yield
            sky.blit(stars, (0, 0), special_flags=pygame.BLEND_RGB_ADD)

        # the moon, paler by day
        mx, my = moon
        if moonAlt > -3 and -60 < mx < W + 60:
            key = (round(elongation, 2), round(math.atan2(sy - my, sx - mx), 1))
            if key != self.moonKey:
                self.moonKey = key
                self.moonImage = self.makeMoon(elongation, sx - mx, sy - my)
            full = (1 - math.cos(elongation)) / 2
            if dark > 0.3:
                glow = tinted(self.moonGlow, (255 * dark * full,) * 3)
                sky.blit(glow, glow.get_rect(center=(round(mx), round(my))), special_flags=pygame.BLEND_RGB_ADD)
            moonImage = tinted(self.moonImage, (255 * (0.5 + 0.5 * dark),) * 3)
            sky.blit(moonImage, moonImage.get_rect(center=(round(mx), round(my))), special_flags=pygame.BLEND_RGB_ADD)

        # the sun, redder near the horizon
        if sunAlt > -2:
            low = float(smoothstep(14, 0, sunAlt))
            colour = np.array((255, 252, 240), np.float32) * (1 - low) + np.array((255, 150, 70), np.float32) * low
            sunImage = tinted(self.sunImage, colour)
            sky.blit(sunImage, sunImage.get_rect(center=(round(sx), round(sy))), special_flags=pygame.BLEND_RGB_ADD)
        self.sky = sky
        yield

    # A cloud, lit from where the sun is (from above when it is high, from below when it has
    # set, and by the city's glow from below at night), with a bright rim when it is near the sun
    def cloudImage(self, cloud):
        shape = cloud["shape"]
        state = self.state
        colours, dark = state["colours"], state["dark"]
        w, h = shape["size"]
        cx, cy = cloud["x"] + w / 2, cloud["y"] + h / 2
        sx, sy = state["sun"]
        dx, dy = sx - cx, sy - cy
        distance = math.hypot(dx, dy) or 1
        lx, ly = dx / distance, dy / distance
        high = float(smoothstep(10, 50, state["sunAlt"]))
        lx, ly = lx * (1 - high), ly * (1 - high) - high
        night = float(smoothstep(0.5, 1.0, dark))
        lx, ly = lx * (1 - night), ly * (1 - night) + night
        length = math.hypot(lx, ly) or 1
        lx, ly = lx / length, ly / length

        facing = shape["nx"] * lx + shape["ny"] * ly
        # bright where it faces the light, and on the side of its height towards the light (the
        # tops by day, the undersides at sunset), each billow lit on its upper side
        light = (0.5 + 0.3 * facing + 0.45 * (shape["height"] - 0.5) * -ly + 0.18 * shape["bumps"] * -ly
                 - 0.12 * shape["thick"] + 0.12 * shape["fine"])
        light = np.clip(light, 0, 1)
        rgb = colours["cloudShade"] + (colours["cloudLit"] - colours["cloudShade"]) * light[..., None]
        alpha = shape["alpha"]
        rim = 0.8 * math.exp(-distance / 280) * float(smoothstep(-4, 2, state["sunAlt"]))
        if rim > 0.02:              # its thin edges shine with the sun close behind
            edge = np.clip(1 - alpha, 0, 1) * alpha * 4 * np.clip(facing, 0, 1)
            rgb = rgb + colours["glow"] * (rim * edge)[..., None]
        alpha = alpha * (0.95 - 0.25 * dark) * (0.75 if shape["streak"] else 1.0) * 255
        return toSurface(rgb, alpha)

    # Puts the light on the rows of buildings: the colour of the daylight, the haze in front of
    # the further rows (see mergeRows), and the street lamps that are on; then the windows that
    # are lit, and the light on the cars, the people and the steam
    def lightCity(self, colours, dark):
        state = self.state
        ambient = colours["ambient"]
        haze = colours["horizon"] * 0.9 + colours["zenith"] * 0.1
        sunAlt, sunAz = state["sunAlt"], state["sunAz"]
        direct = float(smoothstep(-1, 6, sunAlt)) * (1 - 0.6 * state["cloudiness"])     # sunshine, not just daylight
        low = float(smoothstep(20, 0, sunAlt))
        sunColour = np.array((255, 246, 228), np.float32) * (1 - low) + np.array((255, 158, 80), np.float32) * low
        front = max(0.0, math.cos(math.radians(sunAz - FACING - 180))) * direct        # the sun behind you
        light = np.clip(ambient * (0.84 + 0.3 * front), 0, 255)
        reflected = colours["zenith"] * 0.45 + colours["horizon"] * 0.55
        glowsOn = dark > 0.25
        lampsOn = tuple(dark > threshold for _, _, threshold in self.lamps)
        key = (tuple(int(c) // 3 for c in light), tuple(int(c) // 4 for c in haze), lampsOn, glowsOn,
               round(direct * 10), round(sunAz / 6))
        if key == self.lightKey and self.city is not None:
            return
        self.lightKey = key

        # in bands, a frame each, as each takes a while on the Pi
        city = self.albedo.copy()
        w, h = city.get_size()
        bands = [pygame.Rect(0, y, w, min(h, y + h // 2 + 1) - y) for y in (0, h // 2 + 1)]
        for band in bands:
            city.subsurface(band).fill(tuple(int(c) for c in light), special_flags=pygame.BLEND_RGB_MULT)
            yield
        for band in bands:
            mist = self.hazeMask.subsurface(band).copy()
            mist.fill(tuple(int(c) for c in haze), special_flags=pygame.BLEND_RGB_MULT)
            city.blit(mist, band.topleft, special_flags=pygame.BLEND_RGB_ADD)
            yield
        for band in bands:                      # the sky in the window panes
            panes = self.reflectMask.subsurface(band).copy()
            panes.fill(tuple(int(c) for c in reflected), special_flags=pygame.BLEND_RGB_MULT)
            city.blit(panes, band.topleft, special_flags=pygame.BLEND_RGB_ADD)
            yield

        # the sunshine on the sides that face it
        for image, where, normal in self.sides:
            amount = max(0.0, math.cos(math.radians(sunAz - normal))) * direct
            if amount > 0.03:
                city.blit(tinted(image, sunColour * amount * 1.05), where, special_flags=pygame.BLEND_RGB_ADD)
        glow, headY = self.lampGlow
        for (x, y, _), on in zip(self.lamps, lampsOn):
            if on:
                city.blit(glow, (x - glow.get_width() // 2, y - headY - self.cityTop), special_flags=pygame.BLEND_RGB_ADD)
        yield

        lit = city.copy()
        self.glowsOn = glowsOn
        top = self.cityTop
        if glowsOn:
            for window in self.windows:
                if window.on and window.glow is not None:
                    lit.blit(window.glow, window.glowRect.move(0, -top), special_flags=pygame.BLEND_RGB_ADD)
        for window in self.windows:
            if window.on:
                lit.blit(window.lit, window.rect.move(0, -top))
        self.cityBase, self.city = city, lit
        yield

        self.vehicleLight = (light, np.clip((colours["zenith"] * 0.5 + colours["horizon"] * 0.5) * 1.15, 0, 255))
        for model in list(self.carModels):
            self.lightVehicle(model)
            yield
        self.litLamps = [x for (x, _, _), on in zip(self.lamps, lampsOn) if on]
        steam = colours["cloudLit"] * 0.6 + ambient * 0.3
        self.puffsShown = [tinted(p, steam) for p in self.puffs]
        self.contrailShown = tinted(self.contrail, colours["cloudLit"])
        yield
        for walker in self.walkers:
            walker["shown"] = {side: [tinted(f, light * 0.95) for f in walker[side]] for side in ("right", "left")}

    ##--------------------------------------------------------------
    ## Every second or so: which windows are lit
    ##--------------------------------------------------------------

    def windowOn(self, window, dark, m, minutes, weekday):
        kind = window.kind
        if kind == HOME:
            if dark < window.threshold:
                return False
            if not ((window.home <= m < window.a) or m >= window.b):
                return False
            return chance(window.seed, minutes // window.period) > 0.25
        if kind == OFFICE:
            floor = self.floors[window.group]
            if dark < window.threshold * 0.8:
                return False
            if floor["night"]:
                return True
            if not (weekday or floor["weekend"]):
                return False
            if m < floor["end"] or m >= floor["start"]:
                return chance(window.seed, minutes // 1440) > 0.12
            return False
        if kind == SHOP:
            return m >= window.a or m < window.b
        if kind == SIGN:
            return dark > 0.3 and (m >= window.a or m < window.b + 60)
        return dark > window.threshold         # stairs and halls: all night

    def updateWindows(self, now):
        (sunAlt, _), _, _ = sunAndMoon(now.timestamp())
        dark = darknessFor(sunAlt)
        m = (now.hour * 60 + now.minute + now.second / 60 - 720) % 1440     # minutes after noon
        minutes = now.timestamp() / 60
        weekday = now.weekday() < 5 if now.hour >= 5 else (now - datetime.timedelta(days=1)).weekday() < 5
        for window in self.windows:
            on = self.windowOn(window, dark, m, minutes, weekday)
            if on != window.on:
                window.on = on
                if self.city is not None:
                    self.repaint(window)

    # Puts back the wall round a window that has just gone on or off, with the light of the
    # windows near it that are on
    def repaint(self, window):
        top = self.cityTop
        city = self.city
        area = (window.glowRect if self.glowsOn else window.rect).move(0, -top)
        city.set_clip(area)
        city.blit(self.cityBase, area, area)
        group = [window] + window.near
        if self.glowsOn:
            for w in group:
                if w.on and w.glow is not None:
                    city.blit(w.glow, w.glowRect.move(0, -top), special_flags=pygame.BLEND_RGB_ADD)
        for w in group:
            if w.on:
                city.blit(w.lit, w.rect.move(0, -top))
        city.set_clip(None)

    ##--------------------------------------------------------------
    ## Every frame
    ##--------------------------------------------------------------

    def update(self, now):
        t = time.monotonic()
        dt = 0.0 if self.lastT is None else min(0.2, t - self.lastT)
        self.lastT = t
        self.t = t
        if self.offset and t > self.previewUntil:          # back to now
            self.offset = 0.0
            self.stateTime = None
        if self.offset:
            now = now + datetime.timedelta(seconds=self.offset)
        ts = now.timestamp()
        if self.stateTime is None:
            self.stateTime = ts
            self.job = None
            self.updateWindows(now)
            self.refresh(now)
            if not self.clouds:
                self.fillClouds()
        elif self.job is not None:
            try:
                next(self.job)
            except StopIteration:
                self.job = None
        elif abs(ts - self.stateTime) >= REFRESH_SECONDS:
            self.stateTime = ts
            self.job = self.refreshSteps(now)
        if t >= self.windowsDue:
            self.windowsDue = t + 1.0
            self.updateWindows(now)

        night = self.state["dark"] > 0.6
        preview = math.ceil(self.previewUntil - t) if self.offset else None
        key = (now.hour, now.minute, night, preview)
        if key != self.clockKey:
            self.clockKey = key
            self.clockImage = self.makeClock(now, night, preview)

        while self.newModels:                   # vehicles just made, joining the traffic
            model = self.newModels.pop(0)
            self.lightVehicle(model)
            self.carModels.append(model)

        self.moveClouds(dt)
        self.moveCars(dt, now)
        self.movePeople(dt, now)
        self.moveSteam(dt)
        self.moveFlyers(dt, t)

    def fillClouds(self):
        self.clouds = []
        target = self.cloudTarget()
        for _ in range(target):
            self.clouds.append(self.newCloud(self.rng.uniform(-300, W)))

    def cloudTarget(self):
        return round(1 + 11 * self.state["cloudiness"])

    def newCloud(self, x):
        rng = self.rng
        shape = self.cloudShapes[rng.integers(len(self.cloudShapes))]
        y = rng.uniform(30, 470) if not shape["streak"] else rng.uniform(60, 600)
        speed = rng.uniform(5, 9) * (1.2 if y < 250 else 0.85)
        cloud = dict(shape=shape, x=x, y=y, speed=speed)
        cloud["image"] = self.cloudImage(cloud)
        return cloud

    def moveClouds(self, dt):
        for cloud in self.clouds:
            cloud["x"] += cloud["speed"] * dt
        self.clouds = [c for c in self.clouds if c["x"] < W + 20]
        if len(self.clouds) < self.cloudTarget() and self.rng.random() < dt / 20:
            shape = self.cloudShapes[self.rng.integers(len(self.cloudShapes))]
            self.clouds.append(self.newCloud(-shape["size"][0] - 10))
        self.clouds.sort(key=lambda c: c["speed"])

    # How busy the road is at this time of day, in cars a second each way
    @staticmethod
    def traffic(now):
        h = now.hour + now.minute / 60
        level = 0.03 + 0.12 * smoothstep(5.5, 7.5, h) + 0.14 * math.exp(-((h - 8.2) / 1.0) ** 2) + \
            0.12 * math.exp(-((h - 17.5) / 1.4) ** 2) - 0.1 * smoothstep(20, 23.5, h)
        return max(0.02, float(level)) * TRAFFIC

    def moveCars(self, dt, now):
        rng = self.rng
        rate = self.traffic(now)
        for lane in (0, 1):
            direction = LANE_DIRECTION[lane]
            cars = [c for c in self.cars if c["lane"] == lane]
            cars.sort(key=lambda c: -c["x"] * direction)          # the one in front first
            ahead = None
            for car in cars:
                speed = car["want"]
                if ahead is not None:
                    gap = (ahead["x"] - car["x"]) * direction - (ahead["length"] + car["length"]) / 2
                    if gap < 30:
                        speed = min(speed, ahead["speed"] * 0.9)
                    elif gap < 70:
                        speed = min(speed, ahead["speed"])
                car["braking"] = speed < car["want"] * 0.97
                car["speed"] = speed
                car["x"] += speed * direction * dt
                ahead = car
            if TRAFFIC and self.carModels and rng.random() < rate * dt:
                models = self.carModels
                model = models[rng.integers(len(models))]
                while model[lane]["bus"] and rng.random() > 0.35:          # buses less often
                    model = models[rng.integers(len(models))]
                length = model[lane]["length"]
                x = -length if direction > 0 else W + length
                last = cars[-1] if cars else None
                if last is None or (last["x"] - x) * direction > length + last["length"] + 30:
                    self.cars.append(dict(lane=lane, model=model, x=x, length=length, want=rng.uniform(95, 140) * (1.12 if lane else 1.0),
                                          speed=0, braking=False, lights=float(rng.uniform(0.25, 0.5))))
        self.cars = [c for c in self.cars if -400 < c["x"] < W + 400]

    def movePeople(self, dt, now):
        rng = self.rng
        if PEOPLE and TRAFFIC:
            h = now.hour + now.minute / 60
            rate = (0.02 + 0.1 * smoothstep(6.5, 8.5, h) * (1 - smoothstep(19, 23, h))) * TRAFFIC
            if rng.random() < rate * dt and len(self.people) < 9:
                walker = self.walkers[rng.integers(len(self.walkers))]
                direction = 1 if rng.random() < 0.5 else -1
                self.people.append(dict(walker=walker, dir=direction, x=-20 if direction > 0 else W + 20,
                                        y=rng.uniform(STREET_Y + 26, KERB_Y - 10), speed=rng.uniform(26, 38), step=rng.uniform(0, 1)))
        for person in self.people:
            person["x"] += person["speed"] * person["dir"] * dt
            person["step"] = (person["step"] + person["speed"] * dt / (person["walker"]["height"] * 1.3)) % 1
        self.people = [p for p in self.people if -40 < p["x"] < W + 40]
        self.people.sort(key=lambda p: p["y"])

    def moveSteam(self, dt):
        rng = self.rng
        for x, y in self.vents:
            if rng.random() < dt * 1.6:
                self.steam.append(dict(x=x + rng.uniform(-2, 2), y=y, age=0.0, life=rng.uniform(5, 9),
                                       vx=rng.uniform(4, 9), vy=-rng.uniform(9, 15)))
        for puff in self.steam:
            puff["age"] += dt
            puff["x"] += puff["vx"] * dt
            puff["y"] += puff["vy"] * dt
            puff["vy"] *= 1 - 0.08 * dt
        self.steam = [p for p in self.steam if p["age"] < p["life"]]

    def moveFlyers(self, dt, t):
        rng = self.rng
        dark = self.state["dark"]
        if self.flock is None and t > self.nextFlock and dark < 0.55:
            direction = 1 if rng.random() < 0.5 else -1
            count = int(rng.integers(5, 11))
            birds = [dict(dx=-i * rng.uniform(14, 22), dy=(i % 2 * 2 - 1) * i * rng.uniform(4, 8) + rng.uniform(-4, 4),
                          phase=rng.uniform(0, 6.3), rate=rng.uniform(7, 9)) for i in range(count)]
            self.flock = dict(x=-60 if direction > 0 else W + 60, y=rng.uniform(140, 520), dir=direction,
                              speed=rng.uniform(55, 75), birds=birds, drift=rng.uniform(-6, 6))
        if self.flock:
            f = self.flock
            f["x"] += f["speed"] * f["dir"] * dt
            f["y"] += f["drift"] * dt
            if not -300 < f["x"] < W + 300:
                self.flock = None
                self.nextFlock = t + rng.uniform(60, 200)

        if self.plane is None and t > self.nextPlane:
            direction = 1 if rng.random() < 0.5 else -1
            self.plane = dict(x=-30 if direction > 0 else W + 30, y=rng.uniform(80, 330), dir=direction,
                              speed=rng.uniform(26, 40), climb=rng.uniform(-1.5, 1.5))
        if self.plane:
            p = self.plane
            p["x"] += p["speed"] * p["dir"] * dt
            p["y"] += p["climb"] * dt
            if not -500 < p["x"] < W + 500:
                self.plane = None
                self.nextPlane = t + rng.uniform(90, 300)

    ##--------------------------------------------------------------
    ## Drawing
    ##--------------------------------------------------------------

    def draw(self, surface):
        t = self.t
        state = self.state
        surface.blit(self.sky, (0, 0))

        if state["starLevel"] > 0.3:
            twinkles, sprites = self.twinkles
            for x, y, phase, rate in twinkles:
                level = 0.5 + 0.5 * math.sin(t * rate + phase) * math.sin(t * rate * 0.37 + phase * 2)
                sprite = sprites[min(5, int(level * state["starLevel"] * 6))]
                surface.blit(sprite, (x - 4, y - 4), special_flags=pygame.BLEND_RGB_ADD)

        self.drawPlane(surface, t)
        for cloud in self.clouds:
            surface.blit(cloud["image"], (round(cloud["x"]), round(cloud["y"])))
        self.drawFlock(surface, t)

        surface.blit(self.city, (0, self.cityTop))

        dark = state["dark"]
        if dark > 0.35:
            pulse = 0.5 - 0.5 * math.cos(t * 2 * math.pi / 3.0)
            sprite = self.beaconGlows[min(7, int(pulse * min(1, (dark - 0.35) * 3) * 8))]
            for x, y in self.beacons:
                surface.blit(sprite, (x - 14, y - 14), special_flags=pygame.BLEND_RGB_ADD)
        for i, window in enumerate(self.tv):
            if window.on and window.kind == HOME:
                flicker = 0.5 + 0.25 * math.sin(t * 7.3 + i) + 0.25 * math.sin(t * 2.9 + 3 * i) * math.sin(t * 13.1 + i)
                screen = tinted(window.lit, (110 + 80 * flicker, 140 + 90 * flicker, 255))
                surface.blit(screen, window.rect)

        for puff in self.steam:
            k = puff["age"] / puff["life"]
            index = min(len(self.puffsShown) - 1, int(k * len(self.puffsShown)))
            image = self.puffsShown[index]
            image.set_alpha(round(110 * (1 - k) * min(1, puff["age"] * 2)))
            surface.blit(image, image.get_rect(center=(round(puff["x"]), round(puff["y"]))))

        for person in self.people:
            walker = person["walker"]
            if walker["shown"] is None:
                continue
            frames = walker["shown"]["right" if person["dir"] > 0 else "left"]
            image = frames[int(person["step"] * 8) % 8]
            surface.blit(image, (round(person["x"] - image.get_width() / 2), round(person["y"] - image.get_height())))

        for lane in (0, 1):
            for car in self.cars:
                if car["lane"] == lane:
                    self.drawCar(surface, car, dark)

        shadow, where, colon, colonWhere = self.clockImage
        surface.blit(shadow, where)
        breath = 0.5 + 0.5 * math.cos(time.time() * math.pi)
        colon.set_alpha(round(255 * (0.3 + 0.7 * breath)))
        surface.blit(colon, colonWhere)

    def drawCar(self, surface, car, dark):
        lane = car["model"][car["lane"]]
        b = int(np.clip(round((car["x"] - VIEW_X[0]) / (VIEW_X[1] - VIEW_X[0])), 0, len(VIEW_X) - 1))
        version = lane["views"][b]
        image = version["shown"]
        ground = FAR_LANE_Y if car["lane"] == 0 else NEAR_LANE_Y
        ax, ay = version["anchor"]
        x, y = round(car["x"] - ax), round(ground - ay)
        if dark < 0.8:         # its shadow on the road
            shadow = version["shadow"]
            shadow.set_alpha(round(255 * (1 - dark / 0.8)))
            surface.blit(shadow, (round(car["x"] - lane["length"] / 2), ground - shadow.get_height() // 2))
        surface.blit(image, (x, y))
        if self.litLamps and dark > 0.3:                    # caught in the light as it passes under a lamp
            centre = car["x"]
            near = min(abs(centre - lx) for lx in self.litLamps)
            amount = math.exp(-(near / 110) ** 2) * (1.0 if car["lane"] == 0 else 0.6)
            if amount > 0.04:
                lit = version["lamplit"]
                lit.set_alpha(round(255 * amount))
                surface.blit(lit, (x, y))
        if car["braking"] and dark <= car["lights"]:        # brake lights by day
            tx, ty = version["tail"]
            surface.blit(self.tailGlow, (round(x + tx - 9), round(y + ty - 9)), special_flags=pygame.BLEND_RGB_ADD)
        if dark > car["lights"]:
            hx, hy = version["head"]
            tx, ty = version["tail"]
            going = LANE_DIRECTION[car["lane"]]
            beam = self.beam if going > 0 else pygame.transform.flip(self.beam, True, False)
            bx = x + hx if going > 0 else x + hx - beam.get_width()
            surface.blit(beam, (round(bx), ground - beam.get_height() // 2 - 2), special_flags=pygame.BLEND_RGB_ADD)
            surface.blit(self.headGlow, (round(x + hx - 14), round(y + hy - 14)), special_flags=pygame.BLEND_RGB_ADD)
            surface.blit(self.tailGlow, (round(x + tx - 9), round(y + ty - 9)), special_flags=pygame.BLEND_RGB_ADD)
            if car["braking"]:
                surface.blit(self.tailGlow, (round(x + tx - 9), round(y + ty - 9)), special_flags=pygame.BLEND_RGB_ADD)
            if version["inside"] is not None:
                surface.blit(version["inside"], (x, y), special_flags=pygame.BLEND_RGB_ADD)

    def drawFlock(self, surface, t):
        if not self.flock:
            return
        f = self.flock
        colour = (34, 34, 40)
        for bird in f["birds"]:
            bx = f["x"] + bird["dx"] * f["dir"]
            by = f["y"] + bird["dy"]
            flap = math.sin(t * bird["rate"] + bird["phase"])
            span = 7
            tipY = by - 4 * flap
            pygame.draw.aalines(surface, colour, False, [(bx - span, tipY), (bx - 2, by + 0.5), (bx, by + 1.5),
                                                         (bx + 2, by + 0.5), (bx + span, tipY)])

    def drawPlane(self, surface, t):
        if not self.plane:
            return
        p = self.plane
        x, y = round(p["x"]), round(p["y"])
        dark = self.state["dark"]
        if dark < 0.5:
            trail = self.contrailShown if p["dir"] > 0 else pygame.transform.flip(self.contrailShown, True, False)
            tx = x - trail.get_width() if p["dir"] > 0 else x
            surface.blit(trail, (tx, y - trail.get_height() // 2))
            pygame.draw.line(surface, (200, 202, 210), (x - 5, y), (x + 5, y), 2)
            pygame.draw.line(surface, (200, 202, 210), (x - 1, y - 3), (x + 1, y + 3), 1)
        else:
            beat = (t * 1.0) % 1.2
            if beat < 0.06 or 0.16 < beat < 0.22:
                surface.blit(self.strobe, (x - 10, y - 10), special_flags=pygame.BLEND_RGB_ADD)
            if 0.5 < (t * 0.9) % 1.0 < 0.75:
                surface.blit(self.navRed, (x - 7 - 4 * p["dir"], y - 5), special_flags=pygame.BLEND_RGB_ADD)
            pygame.draw.circle(surface, (255, 200, 180), (x, y), 1)
