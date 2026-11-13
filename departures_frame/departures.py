"""
departures.py

An old split-flap board, like a railway station's or an airport's, listing the aircraft
your ADS-B receiver can hear: the flight, where it is going from and to, how far away
it is, its height and what it is doing. Each letter is a little flap that clatters round to the next
letter when it changes, so a new aircraft, or one leaving the list, sets the whole board
rattling. The time in the corner flips over each minute.

The aircraft and their routes come from the LCARS screen, which already
fetches them (see lcars_frame/aircraft.py and lookups.py), so this screen is given that
screen to read them from. As on the LCARS screen, a route is only shown for flights to or
from your own airport (HOME_AIRPORT in lookups.py), as those are the ones likely to be right.

The aircraft are listed in the order they came into range, so the oldest are at the top
and new ones are added at the bottom; when one goes out of range the ones below it move up.
"""

import os
import random
import time
import numpy as np
import pygame
import fonts
import screens as scr
import synth
from lcars_frame import lookups as lk

##==================================================================
## CONFIGURATION
##==================================================================

SOUND = True
SOUND_VOLUME = 0.2              # 0 to 1

# The columns: heading, and how many letters wide
COLUMNS = [("FLIGHT", 7), ("FROM", 11), ("TO", 11), ("DISTANCE", 8), ("HEIGHT", 6), ("STATUS", 10)]
ROWS = 14

TILE_W, TILE_H = 30, 50         # each flap, in pixels...
TILE_GAP = 3                    # ...the space between them...
COLUMN_GAP = 24                 # ...and between the columns
ROW_PITCH = 60
TOP = 196                       # the top of the first row

UPDATE_SECONDS = 10             # the aircraft on the board are brought up to date this often
FLIP_SECONDS = 0.045            # how long a flap takes to fall to the next letter
START_SPREAD = 0.35             # the flaps start up to this long after one another, as on a real board

# The letters on each flap's drum, in the order it goes round them
DRUM = " ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.,-:/'&"

BOARD = (16, 16, 18)
TEXT = (246, 238, 214)
AMBER = (255, 186, 60)
GREEN = (120, 225, 120)
RED = (255, 80, 64)
BLUE = (140, 200, 255)
HEADING = (150, 150, 150)

CLIMB_FPM = 400                 # climbing or descending faster than this, in feet a minute
LOW_FT = 6000                   # below this, a flight from or to our airport is departing or landing


##==================================================================
## THE SOUND OF THE FLAPS
##==================================================================

# One flap hitting the stop: a sharp plastic click with a little ring
def clack(rng):
    t = synth.times(0.05)
    click = synth.noise(0.05, rng)
    click = click - synth.smooth(click, 6)                # take off the low rumble, leaving the snap
    sound = click * np.exp(-t / 0.0025)
    for f, decay, loudness in ((rng.uniform(2200, 3200), 0.006, 0.5), (rng.uniform(800, 1100), 0.01, 0.35)):
        sound += loudness * np.sin(2 * np.pi * f * t) * np.exp(-t / decay)
    return sound


# A couple of seconds of flaps clattering, to play round and round while any are turning
def makeRattle():
    rng = np.random.default_rng(5)
    length = 2.0
    left = np.zeros(int(synth.SAMPLE_RATE * length))
    right = np.zeros_like(left)
    for _ in range(90):
        sound = clack(rng) * rng.uniform(0.3, 1.0)
        at = rng.uniform(0, length - 0.05)
        pan = rng.uniform(0.2, 0.8)
        synth.mixIn(left, sound * (1 - pan), at)
        synth.mixIn(right, sound * pan, at)
    return synth.makeSound(np.column_stack((left, right)), SOUND_VOLUME)


##==================================================================
## THE FLAPS
##==================================================================

def boldFont(size):
    path = os.path.join(fonts.FONT_FOLDER, fonts.FONT_FILE_BOLD)
    try:
        return pygame.font.Font(path, size)
    except (pygame.error, OSError):
        return pygame.font.SysFont("arial", size, bold=True)


# The pictures of each letter on a flap, in each colour: (top half, bottom half), made when first needed
class FlapPictures:

    def __init__(self):
        self.font = boldFont(44)
        ink = self.font.render("H", True, TEXT).get_bounding_rect()
        self.capTop, self.capHeight = ink.top, ink.height
        self.pictures = {}
        self.blank = self.makeBlank()

    # A flap with nothing on it: dark plastic, a little lighter at the top of each half
    def makeBlank(self):
        tile = pygame.Surface((TILE_W, TILE_H), pygame.SRCALPHA)
        tile.fill((0, 0, 0, 0))
        half = TILE_H // 2
        for y in range(TILE_H):
            inHalf = (y % half) / half
            shade = int(44 - 14 * inHalf)
            pygame.draw.line(tile, (shade, shade, shade + 2), (0, y), (TILE_W - 1, y))
        mask = pygame.Surface((TILE_W, TILE_H), pygame.SRCALPHA)
        mask.fill((0, 0, 0, 0))
        pygame.draw.rect(mask, (255, 255, 255, 255), (0, 0, TILE_W, TILE_H), border_radius=3)
        tile.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        return tile

    def get(self, char, colour):
        key = (char, colour)
        if key not in self.pictures:
            tile = self.blank.copy()
            if char != " ":
                glyph = self.font.render(char, True, colour)
                if glyph.get_width() > TILE_W - 4:
                    glyph = pygame.transform.smoothscale(glyph, (TILE_W - 4, glyph.get_height()))
                # every letter sits on the same line, with the capitals in the middle
                tile.blit(glyph, (round((TILE_W - glyph.get_width()) / 2),
                                  round(TILE_H / 2 - self.capTop - self.capHeight / 2)))

            # the split between the two halves, with a glint below it
            half = TILE_H // 2
            pygame.draw.line(tile, (0, 0, 0), (0, half - 1), (TILE_W, half - 1), 2)
            pygame.draw.line(tile, (70, 70, 72), (0, half + 1), (TILE_W, half + 1), 1)

            top = tile.subsurface((0, 0, TILE_W, half)).copy()
            bottom = tile.subsurface((0, half, TILE_W, TILE_H - half)).copy()
            self.pictures[key] = (top, bottom)
        return self.pictures[key]


class Flap:

    def __init__(self, x, y):
        self.x, self.y = x, y
        self.char = " "                 # the letter showing
        self.colour = TEXT
        self.target = " "               # the letter it is turning to
        self.targetColour = TEXT
        self.progress = 0.0             # how far the flap has fallen, 0 to 1
        self.wait = 0.0                 # seconds before it starts turning

    @property
    def turning(self):
        return self.char != self.target or self.colour != self.targetColour

    def nextChar(self):
        return DRUM[(DRUM.index(self.char) + 1) % len(DRUM)]

    # Move on by dt seconds. True if it has changed.
    def update(self, dt):
        if self.wait > 0:
            self.wait -= dt
            return False

        if self.char == self.target:
            self.colour = self.targetColour         # the same letter in another colour: no need to go round
            return True

        self.progress += dt / FLIP_SECONDS
        while self.progress >= 1 and self.char != self.target:
            self.progress -= 1
            self.char = self.nextChar()
            self.colour = self.targetColour
        if self.char == self.target:
            self.progress = 0
        return True

    # Draw it as it is: the next letter's top half above, the last one's bottom half below,
    # and the flap that is falling between them, seen edge on halfway down
    def draw(self, surface, pictures):
        half = TILE_H // 2
        surface.fill(BOARD, (self.x, self.y, TILE_W, TILE_H))
        nowTop, nowBottom = pictures.get(self.char, self.colour)

        if self.char == self.target or self.progress <= 0:
            surface.blit(nowTop, (self.x, self.y))
            surface.blit(nowBottom, (self.x, self.y + half))
            return

        nextTop, nextBottom = pictures.get(self.nextChar(), self.targetColour)
        surface.blit(nextTop, (self.x, self.y))
        surface.blit(nowBottom, (self.x, self.y + half))

        p = self.progress
        if p < 0.5:
            height = max(1, round(half * (1 - 2 * p)))
            flap = pygame.transform.scale(nowTop, (TILE_W, height))
            shade = int(255 * (1 - 0.6 * 2 * p))
            flap.fill((shade, shade, shade), special_flags=pygame.BLEND_RGB_MULT)
            surface.blit(flap, (self.x, self.y + half - height))
        else:
            height = max(1, round(half * (2 * p - 1)))
            flap = pygame.transform.scale(nextBottom, (TILE_W, height))
            shade = int(255 * (0.4 + 0.6 * (2 * p - 1)))
            flap.fill((shade, shade, shade), special_flags=pygame.BLEND_RGB_MULT)
            surface.blit(flap, (self.x, self.y + half))


##==================================================================
## WHAT THE BOARD SAYS
##==================================================================

def fit(text, width):
    text = "".join(c if c in DRUM else " " for c in (text or "").upper())
    return text[:width].ljust(width)


def distanceText(miles):
    if miles is None:
        return ""
    return f"{round(miles)} NM"         # whole miles, or the board would clatter all the time


def heightText(feet):
    if feet is None:
        return ""
    return f"{feet:,}" if feet < 100000 else f"{feet // 1000}K"


# What an aircraft is doing, and the colour to say it in
def status(plane, route):
    if plane.emergency:
        return "EMERGENCY", RED
    if plane.service:
        return plane.service, BLUE
    if plane.military:
        return "MILITARY", BLUE

    rate = plane.vertical_rate_fpm or 0
    low = plane.altitude_ft is not None and plane.altitude_ft < LOW_FT
    if route and low and rate < -CLIMB_FPM and route.destination == lk.HOME_AIRPORT:
        return "LANDING", GREEN
    if route and low and rate > CLIMB_FPM and route.origin == lk.HOME_AIRPORT:
        return "DEPARTED", GREEN
    if rate > CLIMB_FPM:
        return "CLIMBING", AMBER
    if rate < -CLIMB_FPM:
        return "DESCENDING", AMBER
    return "CRUISING", AMBER


# The letters of one row, with their colours, for an aircraft
def rowFor(plane, routes):
    route = lk.route_at_airport(routes.get(plane.callsign), lk.HOME_AIRPORT) if plane.callsign else None
    words, colour = status(plane, route)

    texts = [
        (plane.callsign or plane.icao, TEXT),
        ((route.origin_name or route.origin) if route else "", TEXT),
        ((route.destination_name or route.destination) if route else "", TEXT),
        (distanceText(plane.distance_nm), TEXT),
        (heightText(plane.altitude_ft), TEXT),
        (words, colour),
    ]

    letters = []
    for (text, colour), (_, width) in zip(texts, COLUMNS):
        if text and _ in ("DISTANCE", "HEIGHT"):
            text = text.rjust(width)
        letters += [(c, colour) for c in fit(text, width)]
    return letters


# A row with a message across it, ignoring the columns
def messageRow(text, colour):
    width = sum(w for _, w in COLUMNS)
    return [(c, colour) for c in fit(text, width)]


##==================================================================
## THE SCREEN
##==================================================================

class DeparturesScreen(scr.Screen):

    name = "DEPARTURES"
    hasSound = True

    def soundList(self):
        return [(self.rattle, 1.0)]

    # source is the LCARS screen, whose aircraft, routes and types are shown
    def __init__(self, source):
        self.source = source


    def start(self):
        self.pictures = FlapPictures()
        self.background = self.drawBackground()
        self.board = self.background.copy()

        # the flaps of each row, and of the clock
        self.rows = []
        for r in range(ROWS):
            y = TOP + r * ROW_PITCH
            row = []
            for x in self.columnTiles():
                row.append(Flap(x, y))
            self.rows.append(row)

        clockX = scr.SCREEN_WIDTH - self.margin - 5 * (TILE_W + TILE_GAP) + TILE_GAP
        self.clock = [Flap(clockX + i * (TILE_W + TILE_GAP), 52) for i in range(5)]
        self.flaps = [flap for row in self.rows for flap in row] + self.clock
        for flap in self.flaps:
            flap.draw(self.board, self.pictures)

        self.firstSeen = {}             # icao -> when it was first seen, for the order of the rows
        self.lastRead = 0
        self.lastTicks = pygame.time.get_ticks()
        self.rattle = makeRattle() if SOUND else None
        self.rattleChannel = None


    # The x of each flap along a row, column by column
    def columnTiles(self):
        width = sum(w for _, w in COLUMNS) * (TILE_W + TILE_GAP) - TILE_GAP * len(COLUMNS) + COLUMN_GAP * (len(COLUMNS) - 1)
        self.margin = (scr.SCREEN_WIDTH - width) // 2
        xs = []
        x = self.margin
        for _, letters in COLUMNS:
            for i in range(letters):
                xs.append(x)
                x += TILE_W + TILE_GAP
            x += COLUMN_GAP - TILE_GAP
        return xs


    def drawBackground(self):
        w, h = scr.SCREEN_WIDTH, scr.SCREEN_HEIGHT
        rng = np.random.default_rng(1)
        shade = 1 + rng.normal(0, 0.04, (h, w)) - 0.25 * np.linspace(-1, 1, h)[:, None] ** 2
        rgb = np.array(BOARD, dtype=np.float32) * shade[..., None]
        surface = pygame.surfarray.make_surface(np.clip(rgb, 0, 255).astype(np.uint8).transpose(1, 0, 2))

        self.columnTiles()
        title = boldFont(64).render("FLIGHTS OVERHEAD", True, (255, 255, 255))
        surface.blit(title, (self.margin, 40))
        pygame.draw.rect(surface, AMBER, (self.margin, 128, scr.SCREEN_WIDTH - 2 * self.margin, 4))

        small = boldFont(24)
        x = self.margin
        for heading, letters in COLUMNS:
            image = small.render(heading, True, HEADING)
            surface.blit(image, (x, 150))
            x += letters * (TILE_W + TILE_GAP) + COLUMN_GAP - TILE_GAP
        return surface


    # The board as it should be: a row for each aircraft, oldest first
    def readAircraft(self):
        fetcher = getattr(self.source, "aircraft", None)
        if fetcher is None:
            return [messageRow("NO RECEIVER", AMBER)]

        planes = fetcher.get_aircraft().aircraft
        now = time.time()
        for plane in planes:
            self.firstSeen.setdefault(plane.icao, now)
        here = {plane.icao for plane in planes}
        for icao in list(self.firstSeen):
            if icao not in here:
                del self.firstSeen[icao]

        planes = sorted(planes, key=lambda p: self.firstSeen[p.icao])[:ROWS]
        rows = [rowFor(p, self.source.routeFetcher) for p in planes]

        if not rows:
            error = fetcher.get_error()
            rows = [messageRow("RECEIVER OFFLINE" if error else "NO FLIGHTS IN RANGE", AMBER)]
        return rows


    # Set the flaps of the rows turning to what the board should say
    def setTargets(self):
        rows = self.readAircraft()
        for r, row in enumerate(self.rows):
            letters = rows[r] if r < len(rows) else []
            for i, flap in enumerate(row):
                char, colour = letters[i] if i < len(letters) else (" ", TEXT)
                self.setFlap(flap, char, colour)


    def setClock(self):
        for flap, char in zip(self.clock, time.strftime("%H:%M")):
            self.setFlap(flap, char, TEXT)


    def setFlap(self, flap, char, colour):
        if (char, colour) != (flap.target, flap.targetColour):
            if not flap.turning:
                flap.wait = random.uniform(0, START_SPREAD)
            flap.target, flap.targetColour = char, colour


    # Every flap starts from blank, so the board clatters into life
    def enter(self):
        for flap in self.flaps:
            flap.char, flap.progress = " ", 0
            flap.draw(self.board, self.pictures)
        self.lastRead = 0
        self.lastTicks = pygame.time.get_ticks()


    def leave(self):
        if self.rattleChannel:
            self.rattleChannel.stop()
            self.rattleChannel = None


    def update(self, visible):
        if not visible:
            return

        ticks = pygame.time.get_ticks()
        dt = min(0.1, (ticks - self.lastTicks) / 1000)
        self.lastTicks = ticks

        # the rows change only every UPDATE_SECONDS, so the board isn't always clattering;
        # the clock as soon as the minute changes
        if time.time() - self.lastRead >= UPDATE_SECONDS:
            self.lastRead = time.time()
            self.setTargets()
        self.setClock()

        turning = 0
        for flap in self.flaps:
            if flap.turning:
                if flap.update(dt):
                    flap.draw(self.board, self.pictures)
                if flap.wait <= 0:
                    turning += 1

        self.playRattle(turning)


    # The clatter, louder the more flaps are turning, and fading away when they stop
    def playRattle(self, turning):
        if not self.rattle:
            return

        if turning and self.soundOn:
            if self.rattleChannel is None or not self.rattleChannel.get_busy():
                self.rattleChannel = self.rattle.play(loops=-1)
            if self.rattleChannel:
                self.rattleChannel.set_volume(min(1.0, 0.6 + turning / 50))
        elif self.rattleChannel:
            self.rattleChannel.fadeout(150)
            self.rattleChannel = None


    def draw(self, surface):
        surface.blit(self.board, (0, 0))
