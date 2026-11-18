"""
astro.py

An astronomical clock, drawn on a pale panel in a gold border, among great gold scrolls with
acanthus leaves and bell flowers, with grey clockwork behind its three beaded gold dials,
seen through their open middles:

  TIME      a cream ring of Roman numerals (bottom right), with two arrow hands
  MOON      a pale blue ring of the moon's eight phases (top right), new at the top and full at
            the bottom: its hand points to how far through its month the moon is
  ZODIAC    a deep blue ring of the twelve signs (left), with the sun and the moon each going
            round it on a hand of its own, in the sign it is in (the sun moves into the next
            sign about the 20th of each month, and the moon in two or three days)

The wheels behind jump on at each second, with a tick, as though an escapement drove them,
each as fast as its teeth make it. A little carillon of bells plays a phrase at the quarters
(one bar at a quarter past, two at half past, three at a quarter to and all four on the hour),
then a deeper bell strikes the hour.
"""

import math
import pygame
import numpy as np
import screens as scr
from .common import (Face, SS, SERIF_FONTS, polarGrid, screenGrid, smoothstep, waves, toSurface,
                     vignette, sysFont, makeHand, makeShadow, taper, bellStroke, tickStroke,
                     mixNotes, makeSound)
from .city import j2000

##==================================================================
## SETTINGS (they are in settings.py, next to lcars.py)
##==================================================================

from settings import (
    ASTRO_STRIKE_HOURS as STRIKE_HOURS,
    ASTRO_WHEEL_SPEED as WHEEL_SPEED,
    ASTRO_TIME_CENTRE as TIME_CENTRE,
    ASTRO_MOON_CENTRE as MOON_CENTRE,
    ASTRO_ZODIAC_CENTRE as ZODIAC_CENTRE,
    ASTRO_RING_OUTER as RING_OUTER,
    ASTRO_RING_INNER as RING_INNER,
    ASTRO_PAPER as PAPER,
    ASTRO_GOLD as GOLD,
    ASTRO_GOLD_DARK as GOLD_DARK,
    ASTRO_OUTLINE as OUTLINE,
    ASTRO_WHEELS as WHEELS,
    ASTRO_ZODIAC_BLUE as ZODIAC_BLUE,
    ASTRO_ZODIAC_SIGNS as ZODIAC_SIGNS,
    ASTRO_MOON_BLUE as MOON_BLUE,
    ASTRO_MOON_DARK as MOON_DARK,
    ASTRO_MOON_LIGHT as MOON_LIGHT,
    ASTRO_CREAM as CREAM,
    ASTRO_INK as INK,
    ASTRO_HAND as HAND,
)

BEZEL = 16                      # the beaded gold band round each dial
BORDER = 16                     # the gold border's distance from the edge of the screen
FS = 2                          # the scrollwork and the dials are drawn this many times bigger, then shrunk
ZODIAC_TOP = 105                # the longitude at the top of the zodiac (the middle of Cancer), so that
                                # Aries is at 9 o'clock, as in the painting


##==================================================================
## THE SUN AND THE MOON
##==================================================================

# Where the sun and the moon are along the ecliptic (degrees from the start of Aries) at Unix
# time ts. Good to a degree or so, as the city face's sky is.
def longitudes(ts):
    d = j2000(ts)
    g = math.radians(357.529 + 0.98560028 * d)
    sun = 280.459 + 0.98564736 * d + 1.915 * math.sin(g) + 0.020 * math.sin(2 * g)
    m = math.radians(134.963 + 13.064993 * d)
    moon = 218.316 + 13.176396 * d + 6.289 * math.sin(m)
    return sun % 360, moon % 360


##==================================================================
## THE SOUNDS
##==================================================================

# The carillon's tune, a bar at each quarter: (note, beats)
TUNE = [
    [("F#5", 1), ("A5", 1), ("D6", 1), ("A5", 1)],
    [("B5", 1), ("G5", 1), ("E5", 1), ("A5", 1)],
    [("F#5", 1), ("D5", 1), ("E5", 1), ("G5", 1)],
    [("F#5", 1), ("E5", 1), ("D5", 2)],
]
BEAT_SECONDS = 0.46
STRIKE = 220.0                  # the hour bell: A3
STRIKE_GAP = 2.4
STRIKE_DELAY = 1.8              # after the tune, before the first stroke of the hour

NOTE_NAMES = {"C": -9, "D": -7, "E": -5, "F": -4, "G": -2, "A": 0, "B": 2}

def frequency(note):
    semitones = NOTE_NAMES[note[0]] + (1 if "#" in note else 0) + 12 * (int(note[-1]) - 4)
    return 440.0 * 2 ** (semitones / 12)


# The phrases for each quarter (0 is the hour), the hour bell, and the tick and the tock
def makeSounds(chimeVolume, tickVolume):
    bells = {}
    for bar in TUNE:
        for note, _ in bar:
            if note not in bells:
                bells[note] = bellStroke(frequency(note), 3.0, decayScale=0.55, hammer=0.03)

    chimes = {}
    for quarter, bars in ((1, 1), (2, 2), (3, 3), (0, 4)):
        notes, at = [], 0.0
        for bar in TUNE[:bars]:
            for note, beats in bar:
                pan = 0.3 + 0.4 * (frequency(note) - 580) / 600
                notes.append((at, bells[note], 0.7, min(0.8, max(0.2, pan))))
                at += beats * BEAT_SECONDS
        chimes[quarter] = makeSound(mixNotes(notes), chimeVolume)

    strike = makeSound(bellStroke(STRIKE, 6.0, decayScale=1.1), chimeVolume)
    ticks = [makeSound(tickStroke(1.5, 0.011, 0.45, case=0.35), tickVolume),
             makeSound(tickStroke(1.38, 0.012, 0.45, case=0.35), tickVolume * 0.9)]
    return chimes, strike, ticks


# How long the tune for this quarter takes
def tuneSeconds(bars):
    return sum(beats for bar in TUNE[:bars] for _, beats in bar) * BEAT_SECONDS


##==================================================================
## DRAWING THE SCROLLWORK
#
# Each ornament is a list of shapes in its own pixels: ("poly", points, fill) and ("disc",
# (x, y), radius, fill), drawn in turn, each with a dark line round it. An Ornament puts one
# on the panel: moved, turned, made bigger or smaller, and perhaps mirrored.
##==================================================================

# A curving line, as a turtle would draw it: each segment is (length, curvature at its start,
# curvature at its end), the curvature (1 / radius) going smoothly from one to the other, so
# that a segment whose curvature grows winds into a spiral, as the end of a scroll does
def turtle(segments, start=(0.0, 0.0), heading=0.0, step=1.5):
    x, y = start
    a = heading
    points = [(x, y)]
    for length, k0, k1 in segments:
        n = max(1, int(length / step))
        ds = length / n
        for i in range(n):
            a += (k0 + (k1 - k0) * (i + 0.5) / n) * ds
            x += math.cos(a) * ds
            y += math.sin(a) * ds
            points.append((x, y))
    return points


# Where a fraction t of the way along a line is, and which way it is going there (radians)
def along(points, t):
    i = min(len(points) - 2, max(0, int(t * (len(points) - 1))))
    (x0, y0), (x1, y1) = points[i], points[i + 1]
    return (x0, y0), math.atan2(y1 - y0, x1 - x0)


# The outline of a band along the line, as wide at each point as width(t) says (t from 0 to 1)
def band(points, width):
    left, right = [], []
    n = len(points) - 1
    for i, (x, y) in enumerate(points):
        (ax, ay), (bx, by) = points[max(0, i - 1)], points[min(n, i + 1)]
        length = math.hypot(bx - ax, by - ay) or 1
        nx, ny = -(by - ay) / length, (bx - ax) / length
        w = width(i / n) / 2
        left.append((x + nx * w, y + ny * w))
        right.append((x - nx * w, y - ny * w))
    return left + right[::-1]


# A scroll: a band along the line, thick in the middle and thinning to its ends, which
# finish in a little ball
def scroll(segments, thick, start=(0.0, 0.0), heading=0.0, ends=(0.35, 0.3), fill=GOLD, balls=True):
    points = turtle(segments, start, heading)
    first, last = ends

    def width(t):
        return thick * (first + (1 - first) * smoothstep(0, 0.3, t)) * (last + (1 - last) * smoothstep(1, 0.6, t))

    shapes = [("poly", band(points, width), fill)]
    if balls:
        shapes.append(("disc", points[-1], thick * last * 0.62, fill))
        shapes.append(("disc", points[0], thick * first * 0.62, fill))
    return shapes, points


# An acanthus leaf from base, pointing at angle (radians), its tip curling by bend over its
# length, its outer edge (the right, going along it) scalloped into `lobes`. A two-tone leaf
# has a heart of another colour.
def leaf(base, angle, length, width, bend=0.0, lobes=3, fill=GOLD_DARK, heart=None):
    spine = []
    x, y = base
    n = 36
    for i in range(n + 1):
        t = i / n
        a = angle + bend * t * t
        spine.append((x, y, a, t))
        x += math.cos(a) * length / n
        y += math.sin(a) * length / n

    left, right = [], []
    for x, y, a, t in spine:
        w = width / 2 * math.sin(math.pi * min(1.0, t ** 0.6)) ** 0.7
        outer = w
        if lobes:
            outer *= 1 + 0.28 * (abs(math.sin(math.pi * lobes * t)) ** 0.6 - 0.6) * (1 - t)
        nx, ny = -math.sin(a), math.cos(a)
        left.append((x + nx * outer, y + ny * outer))
        right.append((x - nx * w * 0.8, y - ny * w * 0.8))
    shapes = [("poly", left + right[::-1], fill)]
    if heart:
        shapes += leaf((base[0] + math.cos(angle) * length * 0.1, base[1] + math.sin(angle) * length * 0.1),
                       angle, length * 0.78, width * 0.42, bend * 0.95, 0, heart)
    return shapes


# A bell flower, like a tulip: three petals from a cup, the outer two curling away
def bellFlower(base, angle, size, fill=GOLD_DARK):
    shapes = []
    for side in (-1, 1):
        shapes += leaf(base, angle + side * 0.6, size, size * 0.7, side * 1.2, 0, fill)
    shapes += leaf(base, angle, size * 1.15, size * 0.75, 0, 0, fill)
    shapes += leaf((base[0] - math.cos(angle) * size * 0.12, base[1] - math.sin(angle) * size * 0.12),
                   angle, size * 0.6, size * 0.8, 0, 0, GOLD)
    return shapes


# A small fleur-de-lis, pointing at angle
def fleur(base, angle, size):
    shapes = []
    c, s = math.cos(angle), math.sin(angle)
    for side in (-1, 1):
        shapes += leaf(base, angle + side * 0.9, size * 1.05, size * 0.48, side * 2.2, 0, GOLD)
    shapes += leaf((base[0] - c * size * 0.1, base[1] - s * size * 0.1), angle, size * 1.2, size * 0.58, 0, 0, GOLD_DARK)
    bx, by = base[0] + c * size * 0.08, base[1] + s * size * 0.08
    w, d = size * 0.26, size * 0.08
    shapes.append(("poly", [(bx - s * w - c * d, by + c * w - s * d), (bx + s * w - c * d, by - c * w - s * d),
                            (bx + s * w + c * d, by - c * w + s * d), (bx - s * w + c * d, by + c * w + s * d)], GOLD_DARK))
    for side in (-1, 1):
        shapes += leaf((bx - c * d, by - s * d), angle + math.pi + side * 0.5, size * 0.45, size * 0.22, -side * 1.2, 0, GOLD)
    return shapes


# A run of little dots along a line, between fractions t0 and t1 of the way
def dots(points, t0, t1, count, radius):
    return [("disc", along(points, t0 + (t1 - t0) * i / max(1, count - 1))[0], radius, GOLD_DARK) for i in range(count)]


# Leaves along a line: (fraction of the way, side (1 right, -1 left), length, curl)
def leavesAlong(line, specs, broad=0.6, lobes=3):
    shapes = []
    for t, side, size, bend in specs:
        (x, y), a = along(line, t)
        shapes += leaf((x, y), a + side * 0.7, size, size * broad, -side * bend, lobes, GOLD_DARK, GOLD)
    return shapes


# A big corner scroll, as at the top left of the panel: a great curl at one end, unwinding into
# a long sweep that curls over the other way at its far end, with two smaller scrolls
# branching off it, curling away on either side, and leaves all along them
def cornerScroll():
    main, line = scroll([(290, 1 / 28, 1 / 100), (170, 1 / 100, 0), (210, 0, -1 / 170),
                         (150, -1 / 170, -1 / 48), (150, -1 / 48, -1 / 20)], 46, (0, 0), math.pi * 0.2,
                        ends=(0.3, 0.35))
    (x, y), a = along(line, 0.5)
    first, firstLine = scroll([(110, 0, 1 / 160), (130, 1 / 160, 1 / 42), (120, 1 / 42, 1 / 18)], 28,
                              (x, y), a + 0.55, ends=(0.8, 0.35))
    (x, y), a = along(line, 0.66)
    second, secondLine = scroll([(80, 0, -1 / 120), (100, -1 / 120, -1 / 34), (90, -1 / 34, -1 / 15)], 24,
                                (x, y), a - 1.1, ends=(0.8, 0.35))
    behind = (leavesAlong(line, [(0.3, -1, 120, 0.9), (0.4, 1, 100, 0.8), (0.58, -1, 130, 1.0),
                                 (0.66, 1, 96, 0.9), (0.8, -1, 104, 1.1), (0.9, 1, 70, 1.0)])
              + leavesAlong(firstLine, [(0.25, -1, 80, 0.9), (0.45, 1, 70, 1.0), (0.62, -1, 56, 1.1)])
              + leavesAlong(secondLine, [(0.3, 1, 64, 1.0), (0.5, -1, 50, 1.0)], lobes=2))
    (x, y), a = along(line, 0.05)
    flower = bellFlower((x, y), a + 2.4, 84)
    (x, y), a = along(firstLine, 0.97)
    bud = bellFlower((x, y), a + 2.2, 44)
    return (behind + first + second + main + dots(line, 0.42, 0.56, 5, 3.6) + dots(firstLine, 0.3, 0.5, 3, 2.8)
            + flower + bud)


# A smaller S scroll, curling one way at one end and the other way at the other, with leaves
def sScroll():
    shapes, line = scroll([(170, 1 / 22, 1 / 70), (170, 1 / 70, -1 / 70), (170, -1 / 70, -1 / 22)], 32, (0, 0), 0)
    behind = leavesAlong(line, [(0.24, 1, 60, 1.0), (0.38, -1, 84, 0.9), (0.5, 1, 96, 0.9), (0.64, -1, 70, 1.0),
                                (0.76, 1, 54, 1.0)], lobes=2)
    return behind + shapes + dots(line, 0.44, 0.56, 3, 3.0)


# A spray of scrolls and leaves either side of a stem pointing left, mirrored top and bottom,
# with berries where they meet, as on the right of the panel
def spray():
    shapes = []
    for flip in (1, -1):
        part, line = scroll([(140, 0, flip / 400), (150, flip / 400, flip / 150), (120, flip / 150, flip / 40),
                             (150, flip / 40, flip / 20)], 30, (0, 0), math.pi * (1 + flip * 0.12), ends=(0.6, 0.35))
        behind = leavesAlong(line, [(0.15, flip, 80, 0.8), (0.32, -flip, 96, 0.9), (0.48, flip, 74, 0.9)])
        (x, y), a = along(line, 0.3)
        branch, branchLine = scroll([(70, 0, -flip / 120), (90, -flip / 120, -flip / 34), (80, -flip / 34, -flip / 15)],
                                    22, (x, y), a - flip * 0.9, ends=(0.8, 0.35))
        behind += leavesAlong(branchLine, [(0.3, -flip, 60, 1.0), (0.5, flip, 48, 1.0)], lobes=2)
        (x, y), a = along(line, 0.62)
        flower = bellFlower((x, y), a + flip * 1.6, 64)
        shapes += behind + branch + part + flower
        for i in range(3):
            shapes.append(("disc", (-40 - i * 15, flip * (20 + 10 * (i % 2))), 7.5, GOLD_DARK))
    shapes += leaf((24, 0), math.pi, 190, 52, 0, 3, GOLD_DARK, GOLD)
    for flip in (1, -1):
        shapes += leaf((0, 0), math.pi + flip * 0.55, 120, 46, flip * 0.8, 2, GOLD, GOLD_DARK)
    return shapes


class Ornament:

    def __init__(self, shapes, x, y, scale=1.0, angle=0.0, mirror=False, flip=False):
        self.shapes = shapes
        self.x, self.y = x, y
        self.scale = scale
        self.angle = math.radians(angle)
        self.mirror = -1 if mirror else 1
        self.flip = -1 if flip else 1

    def point(self, x, y):
        x, y = x * self.mirror * self.scale, y * self.flip * self.scale
        c, s = math.cos(self.angle), math.sin(self.angle)
        return ((self.x + x * c - y * s) * FS, (self.y + x * s + y * c) * FS)

    def draw(self, surface):
        line = max(1, round(1.6 * FS))
        for shape in self.shapes:
            if shape[0] == "poly":
                points = [self.point(x, y) for x, y in shape[1]]
                pygame.draw.polygon(surface, shape[2], points)
                pygame.draw.polygon(surface, OUTLINE, points, line)
            else:
                _, (x, y), radius, fill = shape
                centre = self.point(x, y)
                r = radius * self.scale * FS
                pygame.draw.circle(surface, fill, centre, r)
                pygame.draw.circle(surface, OUTLINE, centre, r, line)


# Where the ornaments go on the panel
def ornaments():
    w, h = scr.SCREEN_WIDTH, scr.SCREEN_HEIGHT
    zx, zy = ZODIAC_CENTRE
    tx, ty = TIME_CENTRE
    between = (zx + tx) / 2
    return [
        Ornament(spray(), w - 50, h / 2, 0.85),
        Ornament(spray(), 50, h / 2, 0.85, mirror=True),
        Ornament(cornerScroll(), 120, 360, 0.85, 45, flip=True),
        Ornament(cornerScroll(), 120, h - 360, 0.85, -45),
        Ornament(cornerScroll(), w - 120, 360, 0.72, -38, mirror=True, flip=True),
        Ornament(cornerScroll(), w - 120, h - 360, 0.72, 38, mirror=True),
        Ornament(sScroll(), between - 50, 255, 1.05, 25),
        Ornament(sScroll(), between - 50, h - 255, 1.05, -25, flip=True),
        Ornament(spray(), between + 30, h / 2, 0.42, mirror=True),
        Ornament(fleur((0, 0), math.pi / 2, 30), zx, 62),
        Ornament(fleur((0, 0), -math.pi / 2, 30), zx, h - 62),
        Ornament(fleur((0, 0), 0, 30), tx - RING_OUTER - BEZEL - 24, h / 2),
        Ornament(fleur((0, 0), math.pi / 2, 30), w - 330, 62),
        Ornament(fleur((0, 0), -math.pi / 2, 30), w - 330, h - 62),
    ]


##==================================================================
## DRAWING THE DIALS
##==================================================================

# A ring from RING_INNER to RING_OUTER round centre, cut into `parts` with lines, drawn on a
# picture FS times bigger than the screen
def drawRing(surface, centre, colour, parts, lineColour, offset=0.0):
    cx, cy = centre[0] * FS, centre[1] * FS
    outer, inner = RING_OUTER * FS, RING_INNER * FS
    line = max(1, round(1.6 * FS))

    # a gold band round the outside, set with beads, and a fine gold rim inside
    band = (RING_OUTER + BEZEL) * FS
    pygame.draw.circle(surface, GOLD, (cx, cy), band)
    pygame.draw.circle(surface, OUTLINE, (cx, cy), band, line)
    beads = int(2 * math.pi * (RING_OUTER + BEZEL / 2) / 11)
    for i in range(beads):
        a = 2 * math.pi * i / beads
        bx, by = cx + (outer + BEZEL / 2 * FS) * math.sin(a), cy - (outer + BEZEL / 2 * FS) * math.cos(a)
        pygame.draw.circle(surface, GOLD_DARK, (bx, by), BEZEL * 0.3 * FS)
        pygame.draw.circle(surface, OUTLINE, (bx, by), BEZEL * 0.3 * FS, max(1, line // 2))
    pygame.draw.circle(surface, colour, (cx, cy), outer)
    pygame.draw.circle(surface, (0, 0, 0, 0), (cx, cy), inner)
    pygame.draw.circle(surface, lineColour, (cx, cy), outer, line)
    pygame.draw.circle(surface, lineColour, (cx, cy), inner, line)
    pygame.draw.circle(surface, GOLD, (cx, cy), inner + 2 * line, 2 * line)
    for i in range(parts):
        a = math.radians(offset + i * 360 / parts)
        pygame.draw.line(surface, lineColour, (cx + inner * math.sin(a), cy - inner * math.cos(a)),
                         (cx + outer * math.sin(a), cy - outer * math.cos(a)), line)


# Something on a ring, at angle (degrees clockwise from the top), turned so that its top faces out
def onRing(surface, image, centre, angle):
    image = pygame.transform.rotozoom(image, -angle, 1)
    middle = (RING_OUTER + RING_INNER) / 2 * FS
    a = math.radians(angle)
    surface.blit(image, image.get_rect(center=(round(centre[0] * FS + middle * math.sin(a)),
                                               round(centre[1] * FS - middle * math.cos(a)))))


ROMAN = ["XII", "I", "II", "III", "IIII", "V", "VI", "VII", "VIII", "IX", "X", "XI"]

def drawTimeDial(surface):
    drawRing(surface, TIME_CENTRE, CREAM, 12, INK, 15)
    font = sysFont(SERIF_FONTS, round(46 * FS))
    for hour, numeral in enumerate(ROMAN):
        image = font.render(numeral, True, INK)
        onRing(surface, image, TIME_CENTRE, hour * 30)


ZODIAC = "♈♉♊♋♌♍♎♏♐♑♒♓"
ZODIAC_FONTS = ["dejavusans", "segoeuisymbol", "freeserif", "symbola", "notosanssymbols"]
ZODIAC_NAMES = ["ARI", "TAU", "GEM", "CNC", "LEO", "VIR", "LIB", "SCO", "SGR", "CAP", "AQR", "PSC"]


# The first font that has all twelve signs, or None: a font without one draws it as the box it
# draws for a character it doesn't have (pygame's SysFont puts in another font for a name it
# can't find, so each is tried by its file)
def zodiacFont(size):
    for name in ZODIAC_FONTS:
        path = pygame.font.match_font(name)
        if not path:
            continue
        font = pygame.font.Font(path, size)
        missing = pygame.image.tobytes(font.render("", True, (255, 255, 255)), "RGBA")
        if all(pygame.image.tobytes(font.render(glyph, True, (255, 255, 255)), "RGBA") != missing for glyph in ZODIAC):
            return font
    return None


def drawZodiacDial(surface):
    drawRing(surface, ZODIAC_CENTRE, ZODIAC_BLUE, 12, (16, 52, 110), -ZODIAC_TOP)
    font = zodiacFont(round(48 * FS))
    small = sysFont(SERIF_FONTS, round(24 * FS), bold=True)
    for sign, glyph in enumerate(ZODIAC):
        image = font.render(glyph, True, ZODIAC_SIGNS) if font else small.render(ZODIAC_NAMES[sign], True, ZODIAC_SIGNS)
        onRing(surface, image, ZODIAC_CENTRE, sign * 30 + 15 - ZODIAC_TOP)


# The moon as it looks a fraction phase of the way through its month (0 new, 0.5 full),
# lit from the right as it waxes and from the left as it wanes, radius pixels across
def moonPicture(phase, radius):
    size = int(2 * radius + 4)
    r, _, _, dx, dy = polarGrid(size)
    edge = np.sqrt(np.clip(radius * radius - dy * dy, 0, None))
    k = math.cos(2 * math.pi * phase)
    lit = smoothstep(-1, 1, dx - k * edge) if phase < 0.5 else smoothstep(-1, 1, -k * edge - dx)
    rgb = (np.array(MOON_DARK, np.float32) + (np.array(MOON_LIGHT, np.float32) - MOON_DARK) * lit[..., None])
    ring = np.clip(1.6 - np.abs(r - radius + 1), 0, 1)[..., None]
    rgb = rgb * (1 - ring) + np.array(MOON_DARK, np.float32) * 0.6 * ring
    return toSurface(rgb, np.clip(radius + 0.5 - r, 0, 1) * 255)


def drawMoonDial(surface):
    drawRing(surface, MOON_CENTRE, MOON_BLUE, 8, (40, 76, 120), 22.5)
    for i in range(8):
        onRing(surface, moonPicture(i / 8, 22 * FS), MOON_CENTRE, i * 45)


# The panel, a little uneven, as paper is
def drawPaper():
    w, h = scr.SCREEN_WIDTH, scr.SCREEN_HEIGHT
    xx, yy = screenGrid(w, h)
    rng = np.random.default_rng(71)
    texture = 1 + 0.012 * waves(xx, yy, 6, 120, rng) + 0.006 * rng.standard_normal((h, w))
    rgb = np.array(PAPER, np.float32) * texture[..., None]
    return toSurface(vignette(rgb, xx, yy, 0.22))


# A gold border round the panel: a broad line and a fine one inside it, with a little
# square at each corner
def drawBorder(surface):
    w, h = scr.SCREEN_WIDTH * FS, scr.SCREEN_HEIGHT * FS
    line = max(1, round(1.6 * FS))
    for inset, width in ((BORDER, 9), (BORDER + 16, 3)):
        rect = pygame.Rect(inset * FS, inset * FS, w - 2 * inset * FS, h - 2 * inset * FS)
        outside = rect.inflate(width * FS, width * FS)
        pygame.draw.rect(surface, GOLD, outside, width * FS)
        pygame.draw.rect(surface, OUTLINE, outside, line)
        pygame.draw.rect(surface, OUTLINE, outside.inflate(-2 * width * FS, -2 * width * FS), line)
    for x in (BORDER * FS, w - BORDER * FS):
        for y in (BORDER * FS, h - BORDER * FS):
            square = pygame.Rect(0, 0, 30 * FS, 30 * FS)
            square.center = (x, y)
            pygame.draw.rect(surface, GOLD_DARK, square)
            pygame.draw.rect(surface, OUTLINE, square, line)
            pygame.draw.circle(surface, GOLD, (x, y), 8 * FS)
            pygame.draw.circle(surface, OUTLINE, (x, y), 8 * FS, line)


# The scrollwork and the dials, over the wheels, with a soft shadow under them
def drawFront():
    w, h = scr.SCREEN_WIDTH, scr.SCREEN_HEIGHT
    big = pygame.Surface((w * FS, h * FS), pygame.SRCALPHA)
    big.fill((0, 0, 0, 0))
    drawBorder(big)
    for ornament in ornaments():
        ornament.draw(big)
    drawZodiacDial(big)
    drawMoonDial(big)
    drawTimeDial(big)
    front = pygame.transform.smoothscale(big, (w, h))

    shadow = front.copy()
    shadow.fill((0, 0, 0, 255), special_flags=pygame.BLEND_RGBA_MIN)
    shadow.fill((255, 255, 255, 70), special_flags=pygame.BLEND_RGBA_MULT)
    shadow = pygame.transform.smoothscale(pygame.transform.smoothscale(shadow, (w // 8, h // 8)), (w, h))
    layer = pygame.Surface((w, h), pygame.SRCALPHA)
    layer.fill((0, 0, 0, 0))
    layer.blit(shadow, (6, 9))
    layer.blit(front, (0, 0))
    return layer


##==================================================================
## THE WHEELS
##==================================================================

MODULE = 6.0                    # pixels of pitch radius for each two teeth: the same for all, so they mesh

class Wheel:

    def __init__(self, teeth, centre, style):
        self.teeth = teeth
        self.radius = MODULE * teeth / 2
        self.centre = centre
        self.style = style
        self.phase = 0.0        # its angle at step 0 (degrees clockwise)
        self.speed = 0.0        # degrees it turns at each step

    # Turns this one to mesh with another, which drives it
    def meshWith(self, other):
        dx, dy = self.centre[0] - other.centre[0], self.centre[1] - other.centre[1]
        towards = math.degrees(math.atan2(dx, -dy))            # from the other to this, clockwise from up
        other_part = ((towards - other.phase) * other.teeth / 360) % 1
        self.phase = towards + 180 - (0.5 - other_part) * 360 / self.teeth
        self.speed = -other.speed * other.teeth / self.teeth
        return self

    def draw(self):
        rp = self.radius
        outer, root = rp + MODULE, rp - 1.25 * MODULE
        size = int(2 * outer + 6)
        S = 2
        r, ux, uy, dx, dy = polarGrid(size * S)
        r, dx, dy = r / S, dx / S, dy / S
        angle = np.arctan2(dx, -dy)
        u = (angle * self.teeth / (2 * math.pi)) % 1
        tooth = np.clip((0.3 - np.abs(u - 0.5)) / 0.12 + 0.5, 0, 1)
        edge = root + (outer - root) * tooth
        solid = np.clip(edge - r, 0, 1)

        if self.style == "spokes":
            rim, hub, spokes = root - 0.11 * rp, 0.2 * rp, 6
            frac = (angle * spokes / (2 * math.pi)) % 1
            across = r * np.sin(np.minimum(frac, 1 - frac) * 2 * math.pi / spokes)     # from the nearest spoke's middle
            keep = np.maximum.reduce([np.clip(r - rim, 0, 1), np.clip(hub - r, 0, 1), np.clip(0.05 * rp + 0.5 - across, 0, 1)])
            solid *= keep
        elif self.style == "holes":
            count = 5 if self.teeth > 24 else 4
            ring = 0.55 * rp
            for i in range(count):
                a = 2 * math.pi * i / count
                hx, hy = ring * math.sin(a), -ring * math.cos(a)
                solid *= np.clip(np.hypot(dx - hx, dy - hy) - 0.22 * rp, 0, 1)

        solid *= np.clip(r - max(4.0, 0.06 * rp), 0, 1)     # the hole for its arbor
        alpha = solid * WHEELS[3]
        rgb = np.empty(r.shape + (3,), np.float32)
        rgb[:] = WHEELS[:3]
        image = toSurface(rgb, alpha)
        self.image = pygame.transform.smoothscale(image, (size, size))

    def turned(self, step):
        angle = (self.phase + self.speed * step) % 360
        image = pygame.transform.rotozoom(self.image, -angle, 1)
        return image, image.get_rect(center=self.centre)


# A wheel of `teeth` meshing with both a and b, on the side of the line from a to b that `side` says
def between(a, b, teeth, style, side=1):
    ra, rb = a.radius + MODULE * teeth / 2, b.radius + MODULE * teeth / 2
    (ax, ay), (bx, by) = a.centre, b.centre
    d = math.hypot(bx - ax, by - ay)
    if d > ra + rb:                         # too far apart: on the line, as near as it can be
        f = ra / (ra + rb)
        return Wheel(teeth, (ax + (bx - ax) * f, ay + (by - ay) * f), style)
    x = (d * d + ra * ra - rb * rb) / (2 * d)
    y = math.sqrt(max(0.0, ra * ra - x * x)) * side
    ex, ey = (bx - ax) / d, (by - ay) / d
    return Wheel(teeth, (ax + ex * x - ey * y, ay + ey * x + ex * y), style)


# Next to another wheel, at angle (degrees clockwise from up)
def beside(other, teeth, angle, style):
    d = other.radius + MODULE * teeth / 2
    a = math.radians(angle)
    return Wheel(teeth, (other.centre[0] + d * math.sin(a), other.centre[1] - d * math.cos(a)), style)


# The train of wheels: one behind each dial, joined by a great spoked wheel and an idler, with
# a few more turning off them
def makeWheels():
    zodiac = Wheel(16, ZODIAC_CENTRE, "holes")
    time = Wheel(30, TIME_CENTRE, "holes")
    moon = Wheel(36, MOON_CENTRE, "holes")
    great = between(zodiac, time, 96, "spokes", 1)
    great.speed = WHEEL_SPEED
    idler = between(great, moon, 22, "holes", -1)

    wheels = [great, zodiac.meshWith(great), time.meshWith(great), idler.meshWith(great), moon.meshWith(idler)]
    for parent, teeth, angle, style in ((1, 40, 200, "holes"), (2, 14, 60, "plain"), (2, 24, 150, "holes"),
                                        (4, 18, 320, "plain"), (0, 12, 200, "plain"), (4, 28, 60, "holes"),
                                        (1, 36, 330, "holes"), (11, 26, 300, "plain"), (5, 30, 290, "spokes"),
                                        (4, 40, 110, "spokes"), (14, 16, 160, "plain"), (2, 34, 80, "holes"),
                                        (0, 44, 10, "spokes"), (1, 40, 20, "holes"), (18, 28, 340, "spokes"),
                                        (0, 30, 230, "holes"), (20, 20, 200, "plain")):
        wheels.append(beside(wheels[parent], teeth, angle, style).meshWith(wheels[parent]))
    for wheel in wheels:
        wheel.draw()
    return wheels


##==================================================================
## THE HANDS
##==================================================================

# A fine arrow hand, as in the painting, length long, with a little ring about its arbor
def arrowHand(length):
    return makeHand(length, 14, 14, [
        taper(-14, length - 20, 4, 3),
        ("poly", [(0, length), (-11, length - 30), (0, length - 22), (11, length - 30)]),
        ("poly", [(-7, length * 0.55), (0, length * 0.55 + 8), (7, length * 0.55), (0, length * 0.55 + 3)]),
        ("disc", 0, 9),
        ("hole", 0, 4.5),
    ], (4, 6), HAND)


# A plain hand, carrying the sun or the moon, which are put on upright at its end
def carrierHand(length):
    return makeHand(length, 12, 9, [taper(-12, length, 4, 3), ("disc", 0, 9), ("hole", 0, 4.5)], (4, 6), HAND)


def picture(draw, size):
    big = pygame.Surface((size * SS, size * SS), pygame.SRCALPHA)
    big.fill((0, 0, 0, 0))
    draw(big, size * SS / 2, SS)
    return pygame.transform.smoothscale(big, (size, size))


# The sun, with a face, and rays
def drawSun(surface, c, s):
    rays = []
    for i in range(32):
        a = math.pi * i / 16
        r = (36 if i % 2 else 29) * s
        rays.append((c + r * math.cos(a), c + r * math.sin(a)))
        rays.append((c + 19 * s * math.cos(a + math.pi / 32), c + 19 * s * math.sin(a + math.pi / 32)))
    pygame.draw.polygon(surface, GOLD_DARK, rays)
    pygame.draw.polygon(surface, OUTLINE, rays, max(1, round(1.2 * s)))
    pygame.draw.circle(surface, (246, 206, 70), (c, c), 21 * s)
    pygame.draw.circle(surface, OUTLINE, (c, c), 21 * s, max(1, round(1.4 * s)))
    for ex in (-7, 7):
        pygame.draw.arc(surface, OUTLINE, pygame.Rect(c + (ex - 4) * s, c - 7 * s, 8 * s, 6 * s), 0.3, math.pi - 0.3, max(1, round(1.5 * s)))
    pygame.draw.arc(surface, OUTLINE, pygame.Rect(c - 8 * s, c - 2 * s, 16 * s, 12 * s), math.pi + 0.5, 2 * math.pi - 0.5, max(1, round(1.6 * s)))
    pygame.draw.circle(surface, (236, 160, 60), (c - 11 * s, c + 4 * s), 3 * s)
    pygame.draw.circle(surface, (236, 160, 60), (c + 11 * s, c + 4 * s), 3 * s)


# The moon: a silver crescent
def drawMoon(surface, c, s):
    pygame.draw.circle(surface, (214, 220, 230), (c, c), 22 * s)
    pygame.draw.circle(surface, (0, 0, 0, 0), (c + 11 * s, c - 6 * s), 19 * s)
    mask = pygame.mask.from_surface(surface)
    outline = mask.outline()
    if len(outline) > 2:
        pygame.draw.polygon(surface, (70, 78, 96), outline, max(1, round(1.4 * s)))
    pygame.draw.circle(surface, (150, 156, 170), (c - 12 * s, c - 2 * s), 2 * s)


##==================================================================
## THE FACE
##==================================================================

class AstroFace(Face):

    name = "ASTRO"
    statusColour = (110, 86, 30)
    statusFonts = SERIF_FONTS
    statusItalic = True

    def build(self, chimeVolume, tickVolume):
        self.paper = drawPaper()
        self.front = drawFront()
        self.wheels = makeWheels()
        self.hourHand = arrowHand(0.62 * RING_INNER)
        self.minuteHand = arrowHand(RING_INNER - 6)
        self.phaseHand = arrowHand(RING_INNER - 6)
        self.sunHand = carrierHand(RING_INNER - 4)
        self.moonHand = carrierHand(0.6 * RING_INNER)
        self.sun = picture(drawSun, 80)
        self.moon = picture(drawMoon, 52)
        self.sunShadow = makeShadow(self.sun, (0, 0))[0]
        self.moonShadow = makeShadow(self.moon, (0, 0))[0]
        self.chimes, self.strike, self.ticks = makeSounds(chimeVolume, tickVolume)
        self.key = None

    def sounds(self):
        return list(self.chimes.values()) + [self.strike] + self.ticks

    def tickSounds(self):
        return self.ticks

    def chime(self, hour, minute):
        quarter = minute // 15
        sounds = [(0, self.chimes[quarter])]
        if quarter == 0 and STRIKE_HOURS:
            first = tuneSeconds(4) + STRIKE_DELAY
            sounds += [(first + i * STRIKE_GAP, self.strike) for i in range(hour % 12 or 12)]
        return sounds

    beats = 1

    def beatSound(self, now, beat):
        return self.ticks[now.second % 2]

    def enter(self):
        self.key = None

    # Everything moves on once a second, as the wheels do, so the picture is put together then
    def update(self, now):
        step = math.floor(now.timestamp())
        if step == self.key:
            return
        self.key = step

        image = self.paper.copy()
        for wheel in self.wheels:
            image.blit(*wheel.turned(step))
        image.blit(self.front, (0, 0))

        seconds = now.second + now.minute * 60 + (now.hour % 12) * 3600
        self.hourHand.draw(image, seconds / 120, TIME_CENTRE)
        self.minuteHand.draw(image, (seconds % 3600) / 10, TIME_CENTRE)

        sun, moon = longitudes(step)
        self.phaseHand.draw(image, (moon - sun) % 360, MOON_CENTRE)

        for hand, emblem, shadow, longitude, length in ((self.moonHand, self.moon, self.moonShadow, moon, 0.6 * RING_INNER),
                                                        (self.sunHand, self.sun, self.sunShadow, sun, RING_INNER - 4)):
            angle = longitude - ZODIAC_TOP
            hand.draw(image, angle, ZODIAC_CENTRE)
            a = math.radians(angle)
            x, y = ZODIAC_CENTRE[0] + length * math.sin(a), ZODIAC_CENTRE[1] - length * math.cos(a)
            image.blit(shadow, shadow.get_rect(center=(round(x + 5), round(y + 7))))
            image.blit(emblem, emblem.get_rect(center=(round(x), round(y))))
        self.image = image

    def draw(self, surface):
        surface.blit(self.image, (0, 0))
