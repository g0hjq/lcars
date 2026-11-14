"""
brass.py

The clock's first face: a brass case round an aged ivory dial with Roman numerals, blued
steel hands, and a ticking seconds hand. Through a window at the top of the dial a painted
moon shows the moon's phase, as on an old longcase clock, and three little windows below the
middle show the day, the date and the month.

It chimes the Westminster Quarters, like a mantel clock: one phrase at a quarter past, two
at half past, three at a quarter to, and all four on the hour, followed by a deeper bell
striking the hour. While it is shown it also ticks, gently.
"""

import datetime
import math
import pygame
import numpy as np
import screens as scr
from .common import (AnalogueFace, Hand, SS, LIGHT, polarGrid, smoothstep, waves, toSurface,
                     shadeProfile, dome, drawGlass, blitText, sysFont, makeHand, taper, settle,
                     bellStroke, tickStroke, mixNotes, makeSound, SERIF_FONTS)

##==================================================================
## SETTINGS (they are in settings.py, next to lcars.py)
##==================================================================

from settings import (
    BRASS_STRIKE_HOURS as STRIKE_HOURS,
    BRASS_MOTTO as MOTTO,
    BRASS_EVENING_MOTTO as EVENING_MOTTO,
    BRASS_EVENING_FROM as EVENING_FROM,
    BRASS_SECOND_SETTLE as SECOND_SETTLE,
    BRASS_CLOCK_RADIUS as CLOCK_RADIUS,
    BRASS_CLOCK_CENTRE as CLOCK_CENTRE,
    BRASS_INK as INK,
    BRASS_BRASS as BRASS,
    BRASS_STEEL as STEEL,
    BRASS_STEEL_LIGHT as STEEL_LIGHT,
    BRASS_TEXT_COLOUR as TEXT_COLOUR,
    BRASS_CARD as CARD,
    BRASS_SKY as SKY,
    BRASS_MOON as MOON,
)
import settings

R = CLOCK_RADIUS
DIAL_RADIUS = 0.84 * R          # inside the brass

# Where things are on the dial, in pixels (the settings are fractions of the radius)
MOON_WINDOW_Y = settings.BRASS_MOON_WINDOW_Y * R
MOON_WINDOW_RADIUS = settings.BRASS_MOON_WINDOW_RADIUS * R
CALENDAR_WINDOWS = [(fmt, width * R) for fmt, width in settings.BRASS_CALENDAR_WINDOWS]
CALENDAR_HEIGHT = settings.BRASS_CALENDAR_HEIGHT * R
CALENDAR_Y = settings.BRASS_CALENDAR_Y * R
MOTTO_Y = settings.BRASS_MOTTO_Y * R
HOUR_LENGTH = settings.BRASS_HOUR_LENGTH * R
MINUTE_LENGTH = settings.BRASS_MINUTE_LENGTH * R
SECOND_LENGTH = settings.BRASS_SECOND_LENGTH * R
SECOND_TAIL = settings.BRASS_SECOND_TAIL * R

SYNODIC_MONTH = 29.530588853    # days from one new moon to the next
NEW_MOON = datetime.datetime(2000, 1, 6, 18, 14)    # a new moon to count from


##==================================================================
## THE BELLS
##==================================================================

# Westminster Quarters, in E major: G#, F#, E and B
G_SHARP, F_SHARP, E, B = 830.61, 739.99, 659.26, 493.88
STRIKE_NOTE = 329.63            # the hour bell, E an octave below

PHRASES = [
    (G_SHARP, F_SHARP, E, B),
    (E, G_SHARP, F_SHARP, B),
    (E, F_SHARP, G_SHARP, E),
    (G_SHARP, E, F_SHARP, B),
    (B, F_SHARP, G_SHARP, E),
]

# Which phrases are played at a quarter past, half past, a quarter to and on the hour
QUARTERS = {1: (0,), 2: (1, 2), 3: (3, 4, 0), 0: (1, 2, 3, 4)}

BEAT = 0.62                     # seconds from one note to the next...
PHRASE_SECONDS = 5 * BEAT       # ...and from one phrase to the next (three short notes and a long one, then a rest)
STRIKE_GAP = 2.3                # seconds between the strokes of the hour
STRIKE_DELAY = 1.4              # extra seconds after the last phrase before the first stroke
PANS = {G_SHARP: 0.62, F_SHARP: 0.54, E: 0.46, B: 0.38}     # spread a little, like a row of rods


# The chimes, made from their notes: {quarter: Sound}, the hour's stroke, and the tick and
# the tock
def makeChimes(chimeVolume, tickVolume):
    notes = {f: bellStroke(f, 5.0) for f in PANS}

    chimes = {}
    for quarter, phrases in QUARTERS.items():
        mix = mixNotes([(p * PHRASE_SECONDS + n * BEAT, notes[note], 0.85 if n == 3 else 0.75, PANS[note])
                        for p, phrase in enumerate(phrases)
                        for n, note in enumerate(PHRASES[phrase])])
        chimes[quarter] = makeSound(mix, chimeVolume)

    strike = makeSound(bellStroke(STRIKE_NOTE, 7.0, decayScale=1.8), chimeVolume)
    ticks = [makeSound(tickStroke(1.0, 0.006, 0.55), tickVolume),
             makeSound(tickStroke(0.9, 0.009, 0.4), tickVolume)]
    return chimes, strike, ticks


##==================================================================
## THE BACKGROUND AND THE CLOCK FACE (drawn once)
##==================================================================

def serifFont(size, italic=False):
    return sysFont(SERIF_FONTS, size, italic=italic)


# A dark polished wood, with the clock's shadow on it
def drawBackground():
    w, h = scr.SCREEN_WIDTH, scr.SCREEN_HEIGHT
    rng = np.random.default_rng(7)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)

    # the grain runs across in fine streaks, wandering up and down, with a few broad darker bands
    wander = 18 * waves(xx * 0.3, yy, 6, 140, rng) + 5 * waves(xx, yy, 4, 40, rng)
    v = yy + wander
    rows = np.repeat(rng.normal(0, 1, (h // 2 + 40, 1)), 2, axis=0)[:, 0]
    streaks = np.interp(v, np.arange(len(rows)) - 40, rows)
    bands = np.sin(v * 0.021 + 2 * waves(xx, yy, 3, 400, rng))
    fine = rng.normal(0, 1, (h, w)) * 0.04
    shade = 0.6 + 0.07 * streaks + 0.1 * bands + 0.1 * waves(xx, yy * 3, 5, 300, rng) + fine

    dark = np.array([30, 16, 9], dtype=np.float32)
    light = np.array([86, 50, 26], dtype=np.float32)
    rgb = dark + (light - dark) * np.clip(shade, 0, 1)[..., None]

    # darker at the corners
    cx, cy = w / 2, h / 2
    corner = np.sqrt(((xx - cx) / cx) ** 2 + ((yy - cy) / cy) ** 2)
    rgb *= (1 - 0.45 * smoothstep(0.6, 1.5, corner))[..., None]

    # the clock's shadow, falling down and to the right
    sx, sy = CLOCK_CENTRE[0] + 14, CLOCK_CENTRE[1] + 20
    distance = np.sqrt((xx - sx) ** 2 + (yy - sy) ** 2)
    rgb *= (1 - 0.7 * (1 - smoothstep(R - 25, R + 35, distance)))[..., None]

    return toSurface(rgb)


# The brass case and the dial, without the hands, as a surface 2R across with see-through corners
def drawFace():
    size = 2 * R
    rng = np.random.default_rng(11)
    r, ux, uy, dx, dy = polarGrid(size)

    # --- the brass case: a rounded outer rim, a groove, and a thin bead next to the dial
    rs = np.linspace(0, R + 2, 2000)
    hs = np.zeros_like(rs)
    rimMid, rimHalf = 0.925 * R, 0.075 * R
    hs += np.sqrt(np.clip(1 - ((rs - rimMid) / rimHalf) ** 2, 0, None)) * rimHalf * 0.9
    beadMid, beadHalf = 0.86 * R, 0.014 * R
    hs += np.sqrt(np.clip(1 - ((rs - beadMid) / beadHalf) ** 2, 0, None)) * beadHalf
    diffuse, specular = shadeProfile(r, ux, uy, rs, hs)

    angle = np.arctan2(dy, dx)
    brushed = 1 + 0.05 * np.sin(angle * 900 + 3 * np.sin(angle * 7)) * rng.uniform(0.6, 1, r.shape)
    brass = np.array(BRASS, dtype=np.float32)
    caseRgb = brass * ((0.22 + 0.9 * diffuse) * brushed)[..., None] + np.array([255, 235, 190]) * (0.8 * specular)[..., None]

    # darker in the groove between the rim and the bead
    groove = np.exp(-((r - 0.847 * R) / (0.005 * R)) ** 2) + np.exp(-((r - 0.8745 * R) / (0.004 * R)) ** 2)
    caseRgb *= (1 - 0.6 * groove)[..., None]

    # --- the dial: old ivory paint, a little blotchy, darker at the edge and in the case's shadow
    yy, xx = dy, dx
    blotch = waves(xx, yy, 8, 90, rng) * 0.5 + waves(xx, yy, 6, 25, rng) * 0.25
    grain = rng.normal(0, 1, r.shape)
    ivory = np.array([236, 223, 192], dtype=np.float32)
    aged = np.array([205, 182, 138], dtype=np.float32)
    age = np.clip(0.25 + 0.18 * blotch + 0.45 * smoothstep(0.45 * R, DIAL_RADIUS, r), 0, 1)
    dialRgb = ivory + (aged - ivory) * age[..., None] + (grain * 3)[..., None]

    # the case stands up from the dial, so its shadow falls on the side away from the light
    shift = 0.022 * R
    sr = np.sqrt((dx - LIGHT[0] * -shift) ** 2 + (dy - LIGHT[1] * -shift) ** 2)
    shadow = smoothstep(DIAL_RADIUS - 0.05 * R, DIAL_RADIUS + 0.01 * R, sr)
    dialRgb *= (1 - 0.5 * shadow)[..., None]

    inDial = np.clip(DIAL_RADIUS + 0.5 - r, 0, 1)[..., None]
    rgb = dialRgb * inDial + caseRgb * (1 - inDial)
    alpha = np.clip(R - 0.5 - r, 0, 1) * 255

    face = toSurface(rgb, alpha)
    face.blit(drawDialMarks(), (0, 0))
    return face


# The face with a motto on it, below the middle, as some old clocks have
def withMotto(face, motto):
    face = face.copy()
    font = serifFont(round(0.042 * R * SS), italic=True)
    text = font.render(motto, True, INK)
    w, h = text.get_size()
    text = pygame.transform.smoothscale(text, (round(w / SS), round(h / SS)))
    face.blit(text, text.get_rect(center=(R, R + MOTTO_Y)))
    return face


# The rings, the minute marks and the numerals, drawn big and shrunk to make them smooth
def drawDialMarks():
    big = 2 * R * SS
    c = R * SS
    marks = pygame.Surface((big, big), pygame.SRCALPHA)
    marks.fill((*INK, 0))

    def ring(radius, width):
        pygame.draw.circle(marks, INK, (c, c), round(radius * SS), round(width * SS))

    def point(radius, angle):
        a = math.radians(angle)
        return c + radius * SS * math.sin(a), c - radius * SS * math.cos(a)

    # the minute track, between two rings
    outer, inner = 0.795 * R, 0.745 * R
    ring(outer, 2)
    ring(inner, 1.4)
    for minute in range(60):
        if minute % 5:
            pygame.draw.line(marks, INK, point(inner, minute * 6), point(outer, minute * 6), round(1.6 * SS))
        else:
            pygame.draw.circle(marks, INK, point((inner + outer) / 2, minute * 6), round(5 * SS))

    # a thin ring inside the numerals
    ring(0.535 * R, 1.4)
    ring(0.52 * R, 0.8)

    # the numerals, standing on the inner ring and leaning out from the middle
    font = serifFont(round(0.135 * R * SS))
    numerals = ["XII", "I", "II", "III", "IIII", "V", "VI", "VII", "VIII", "IX", "X", "XI"]
    for hour, numeral in enumerate(numerals):
        x, y = point(0.64 * R, hour * 30)
        blitText(marks, font, numeral, INK, x, y, hour * 30)

    return pygame.transform.smoothscale(marks, (2 * R, 2 * R))


##==================================================================
## THE HANDS
##==================================================================

def steelHand(length, tail, halfWidth, shapes, shadowOffset):
    return makeHand(length, tail, halfWidth, shapes, shadowOffset, STEEL, STEEL_LIGHT)


# Breguet hands: a slim shaft, an open ring near the end, then a fine point
def makeHands():
    L = HOUR_LENGTH
    ringY, ringR, holeR = 0.64 * L, 0.12 * L, 0.07 * L
    hour = steelHand(L, 0.12 * L, ringR + 2, [
        taper(-0.12 * L, ringY, 22, 12),
        ("disc", -0.12 * L, 12),
        ("disc", ringY, ringR),
        ("hole", ringY, holeR),
        taper(ringY + holeR, L, 16, 0),
        ("disc", 0, 20),
    ], (5, 7))

    L = MINUTE_LENGTH
    ringY, ringR, holeR = 0.76 * L, 0.06 * L, 0.035 * L
    minute = steelHand(L, 0.1 * L, ringR + 2, [
        taper(-0.1 * L, ringY, 16, 8),
        ("disc", -0.1 * L, 9),
        ("disc", ringY, ringR),
        ("hole", ringY, holeR),
        taper(ringY + holeR, L, 12, 0),
        ("disc", 0, 17),
    ], (8, 11))

    L = SECOND_LENGTH
    second = steelHand(L, SECOND_TAIL, 16, [
        taper(-SECOND_TAIL, L, 5, 1.5),
        ("disc", -0.8 * SECOND_TAIL, 13),
        ("hole", -0.8 * SECOND_TAIL, 6),
        ("disc", 0, 9),
    ], (11, 15))

    return hour, minute, second


##==================================================================
## THE MOON AND THE CALENDAR WINDOWS
##==================================================================

# How far through its month the moon is: 0 new, 0.25 first quarter, 0.5 full...
def moonPhase(now):
    days = (now - NEW_MOON).total_seconds() / 86400
    return (days / SYNODIC_MONTH) % 1


# The moon window, as on an old longcase clock: a big disc painted with a night sky and two
# moons turns slowly behind a half-round window, whose two humps hide the moon as it comes
# and goes, making its phases. Returns the window's picture and where its flat side's
# middle is in it.
def drawMoonWindow(phase):
    a = MOON_WINDOW_RADIUS
    w, h = int(2 * a + 10), int(a + 10)
    ox, oy = w / 2, a + 5
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    x, y = xx + 0.5 - ox, yy + 0.5 - oy

    # the window: inside the half circle, but not in either hump (minus inside, plus outside)
    edge = np.maximum.reduce([np.hypot(x, y) - a, y,
                              a / 2 - np.hypot(x + a / 2, y), a / 2 - np.hypot(x - a / 2, y)])
    inside = np.clip(0.5 - edge, 0, 1)

    # the disc turns about a point well below the window; the moon crosses from left to
    # right, peeping out from behind the left hump as it waxes and going behind the right one
    # as it wanes
    turn = 2.5 * a
    pivotY = -a / 2 + turn
    angle = math.asin((phase - 0.5) * 2.6 * a / turn)
    mx, my = turn * math.sin(angle), pivotY - turn * math.cos(angle)

    # the sky, a little lighter towards the bottom, with stars painted on the disc
    rgb = np.empty((h, w, 3), dtype=np.float32)
    rgb[:] = SKY
    rgb *= (0.8 + 0.35 * np.clip((y + a) / a, 0, 1))[..., None]
    rng = np.random.default_rng(3)
    for _ in range(90):
        sa = rng.uniform(-math.pi, math.pi) + angle
        sr = rng.uniform(turn - 1.1 * a, turn + 0.2 * a)
        sx, sy = sr * math.sin(sa), pivotY - sr * math.cos(sa)
        size = rng.uniform(0.6, 1.4)
        glow = np.exp(-((x - sx) ** 2 + (y - sy) ** 2) / (size * size))
        rgb += glow[..., None] * np.array([235, 215, 150], dtype=np.float32)

    # the moon, gold, a little rounded by the light, with a few darker seas
    radius = a / 2 * 0.94
    dx, dy = x - mx, y - my
    dist = np.hypot(dx, dy)
    moon = np.clip(radius - dist + 0.5, 0, 1)
    domed = np.sqrt(np.clip(1 - (dist / radius) ** 2, 0, 1))
    lit = 0.65 + 0.35 * np.clip((-dx * 0.5 - dy * 0.6) / radius + domed, 0, 1.2)
    seas = np.zeros_like(x)
    for sx, sy, sr in ((-0.3, -0.25, 0.28), (0.25, 0.1, 0.22), (-0.1, 0.35, 0.18), (0.35, -0.35, 0.12)):
        seas += np.exp(-((dx / radius - sx) ** 2 + (dy / radius - sy) ** 2) / (sr * sr))
    moonRgb = np.array(MOON, dtype=np.float32) * (lit * (1 - 0.18 * np.clip(seas, 0, 1)))[..., None]
    rgb = rgb * (1 - moon[..., None]) + moonRgb * moon[..., None]

    # set back into the dial, so darker near the edge of the window, which is outlined
    rgb *= (1 - 0.55 * np.exp(np.minimum(edge, 0) / 5))[..., None]
    outline = np.clip(1.6 - np.abs(edge + 0.4), 0, 1)
    rgb = rgb * (1 - outline[..., None]) + np.array(INK, dtype=np.float32) * outline[..., None]
    alpha = np.maximum(inside, outline) * 255

    return toSurface(rgb, alpha), (ox, oy)


# The three little windows of the calendar, side by side: the day, the date and the month,
# printed on wheels behind the dial. Returns their picture.
def drawCalendar(now):
    gap = round(0.025 * R)
    height = round(CALENDAR_HEIGHT)
    widths = [round(width) for _, width in CALENDAR_WINDOWS]
    surface = pygame.Surface((sum(widths) + gap * (len(widths) - 1), height), pygame.SRCALPHA)
    surface.fill((0, 0, 0, 0))
    font = serifFont(round(0.062 * R))

    # each wheel is round, so darker towards its top and bottom, and the dial's edge shades its top
    yy = (np.arange(height) + 0.5) / height * 2 - 1
    shade = (1 - 0.3 * yy ** 2) * (1 - 0.45 * np.exp(-(np.arange(height) / 4.0)))

    x = 0
    for (fmt, _), width in zip(CALENDAR_WINDOWS, widths):
        rgb = np.empty((height, width, 3), dtype=np.float32)
        rgb[:] = CARD
        rgb *= shade[:, None, None]
        card = toSurface(rgb)
        text = now.strftime(fmt).upper()
        image = font.render(text, True, INK)
        card.blit(image, image.get_rect(center=(width / 2, height / 2 + 1)))
        surface.blit(card, (x, 0))
        pygame.draw.rect(surface, INK, (x, 0, width, height), 2)
        x += width + gap

    return surface


# The face with the day's moon and calendar on it
def withWindows(face, now):
    face = face.copy()
    moon, (ox, oy) = drawMoonWindow(moonPhase(now))
    face.blit(moon, (round(R - ox), round(R - MOON_WINDOW_Y - oy)))
    calendar = drawCalendar(now)
    face.blit(calendar, calendar.get_rect(center=(R, R + CALENDAR_Y)))
    return face


##==================================================================
## THE FACE
##==================================================================

class BrassFace(AnalogueFace):

    name = "BRASS"
    centre = CLOCK_CENTRE
    radius = R
    statusColour = TEXT_COLOUR
    statusFonts = SERIF_FONTS
    statusItalic = True

    def build(self, chimeVolume, tickVolume):
        self.background = drawBackground()
        face = drawFace()
        self.faces = {motto: withMotto(face, motto) for motto in (MOTTO, EVENING_MOTTO)}
        self.date = None                # the date of the moon and the calendar on the dial
        self.dayFaces = None
        self.hands = makeHands()
        self.nut = dome(13, BRASS)
        self.glass = drawGlass(R, DIAL_RADIUS)
        self.chimes, self.strike, self.ticks = makeChimes(chimeVolume, tickVolume)

    def sounds(self):
        return list(self.chimes.values()) + [self.strike] + self.ticks

    def tickSounds(self):
        return self.ticks

    def dialFor(self, now):
        if now.date() != self.date:
            self.date = now.date()
            self.dayFaces = {motto: withWindows(face, now) for motto, face in self.faces.items()}
        return self.dayFaces[EVENING_MOTTO if now.hour >= EVENING_FROM else MOTTO]

    # The seconds hand jumps from one second to the next, and settles
    def angles(self, now):
        hours, minutes, _ = super().angles(now)
        fraction = now.microsecond / 1e6
        return hours, minutes, (now.second - 1 + settle(fraction, SECOND_SETTLE)) * 6

    def chime(self, hour, minute):
        quarter = minute // 15
        sounds = [(0, self.chimes[quarter])]
        if quarter == 0 and STRIKE_HOURS:
            first = len(QUARTERS[0]) * PHRASE_SECONDS + STRIKE_DELAY
            sounds += [(first + i * STRIKE_GAP, self.strike) for i in range(hour % 12 or 12)]
        return sounds

    # Tick, tock, once a second
    beats = 1

    def beatSound(self, now, beat):
        return self.ticks[now.second % 2]
