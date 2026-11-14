"""
deco.py

An Art Deco mantel clock, standing on a marble mantelpiece in front of a wall papered with
gold fans: a black lacquer case with a stepped base and chrome lines, a stepped chrome bezel,
and a champagne sunburst dial with tall, narrow numerals and black lozenge hands.

Its seconds hand beats DECO_BEATS times a second (three), with a light, quick, high tick, and it plays a ding-dong
chime at the quarters (one at a quarter past, two at half past, three at a quarter to, and four
on the hour), then strikes the hour on a deep coiled gong.
"""

import math
import os
import pygame
import numpy as np
import screens as scr
import fonts
import synth
from .common import (AnalogueFace, SS, LIGHT, polarGrid, screenGrid, smoothstep, waves, toSurface,
                     lighting, bevel, chrome, roundedBox, vignette, dome, drawGlass, blitText,
                     makeHand, taper, settle, bellStroke, mixNotes, makeSound, ROD_PARTIALS)

##==================================================================
## SETTINGS (they are in settings.py, next to lcars.py)
##==================================================================

from settings import (
    DECO_BEATS as BEATS,
    DECO_STRIKE_HOURS as STRIKE_HOURS,
    DECO_CENTRE as CENTRE,
    DECO_DIAL_RADIUS as DIAL_RADIUS,
    DECO_RADIUS as RADIUS,
    DECO_BODY_RADIUS as BODY_RADIUS,
    DECO_MANTEL_Y as MANTEL_Y,
    DECO_BLOCKS as BLOCKS,
    DECO_SPEED_LINES as SPEED_LINES,
    DECO_SPEED_LINE_HALF as SPEED_LINE_HALF,
    DECO_LACQUER as LACQUER,
    DECO_CHROME as CHROME,
    DECO_CHAMPAGNE as CHAMPAGNE,
    DECO_INK as INK,
    DECO_HAND as HAND,
    DECO_HAND_LIGHT as HAND_LIGHT,
    DECO_WALL as WALL,
    DECO_GOLD as GOLD,
    DECO_MARBLE as MARBLE,
    DECO_VEIN as VEIN,
)


##==================================================================
## THE SOUNDS
##==================================================================

DING, DONG = 659.26, 523.25     # E and C, like a doorbell
GONG = 174.61                   # F, for the hour
PAIR_SECONDS = 1.7              # from one ding-dong to the next
DONG_AFTER = 0.62
STRIKE_GAP = 2.2
STRIKE_DELAY = 1.6              # after the last ding-dong, before the first stroke of the hour

# A coiled wire gong: deep, with its overtones a little out of tune
GONG_PARTIALS = [(1.0, 1.0, 2.6), (2.02, 0.5, 1.6), (3.1, 0.32, 1.0), (4.3, 0.2, 0.6),
                 (5.6, 0.12, 0.4), (7.1, 0.06, 0.25)]


def makeChimes(chimeVolume, tickVolume):
    ding = bellStroke(DING, 3.5, partials=ROD_PARTIALS, hammer=0.03)
    dong = bellStroke(DONG, 3.5, partials=ROD_PARTIALS, hammer=0.03)
    chimes = {}
    for quarter, pairs in ((1, 1), (2, 2), (3, 3), (0, 4)):
        notes = []
        for i in range(pairs):
            notes.append((i * PAIR_SECONDS, ding, 0.8, 0.56))
            notes.append((i * PAIR_SECONDS + DONG_AFTER, dong, 0.8, 0.44))
        chimes[quarter] = makeSound(mixNotes(notes), chimeVolume)

    gong = makeSound(bellStroke(GONG, 7.0, decayScale=1.3, partials=GONG_PARTIALS, hammer=0.02), chimeVolume)
    ticks = [makeSound(brightTick(1.0, 61), tickVolume * 0.8),
             makeSound(brightTick(0.93, 62), tickVolume * 0.7)]
    return chimes, gong, ticks


# The tick of a small, quick lever movement in a metal case: a sharp click with a short, high
# ring of steel, the tooth dropping a moment later, and hardly any knock from the case. pitch
# scales the ring, so that the tock can be a little lower than the tick.
TICK_RING = [(3300, 0.5, 0.004), (4900, 0.35, 0.0025), (7100, 0.2, 0.0015)]    # (Hz, loudness, seconds to die away)
TICK_BODY = (1900, 0.12, 0.005)     # the little that is heard of the case

def brightTick(pitch, seed):
    t = synth.times(0.06)
    rng = np.random.default_rng(seed)
    sound = np.zeros_like(t)
    for at, loudness in ((0.0, 1.0), (0.0035, 0.45)):
        tt = np.maximum(t - at, 0)
        on = t >= at
        click = synth.noise(0.06, rng)
        click = click - synth.smooth(click, 3)              # only the hiss of it: no thump
        part = 0.7 * click * np.exp(-tt / 0.0006)
        for f, amp, decay in TICK_RING:
            part += amp * np.sin(2 * math.pi * f * pitch * tt + rng.uniform(0, 6.3)) * np.exp(-tt / decay)
        f, amp, decay = TICK_BODY
        part += amp * np.sin(2 * math.pi * f * tt) * np.exp(-tt / decay)
        sound += loudness * part * on * np.minimum(1.0, tt / 0.0002)
    sound *= np.minimum(1.0, (t[-1] - t) / 0.01)
    return sound / np.max(np.abs(sound))


##==================================================================
## DRAWING
##==================================================================

def decoFont(size):
    try:
        return pygame.font.Font(os.path.join(fonts.FONT_FOLDER, fonts.FONT_FILE_BOLD), size)
    except (pygame.error, OSError):
        return pygame.font.SysFont("arial", size, bold=True)


# How far each pixel is from the edge of the case (minus inside): the round body and the
# blocks below it, but not the chrome strip
def caseDistance(xx, yy):
    cx, cy = CENTRE
    d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) - BODY_RADIUS
    for half, top, bottom, corner, isChrome in BLOCKS:
        if not isChrome:
            d = np.minimum(d, roundedBox(xx, yy, cx, (top + bottom) / 2, half, (bottom - top) / 2, corner))
    return d


# Gold fans on dark green paper, in rows, each row half a fan along from the last
def wallpaper(xx, yy):
    fw, fh, radius = 160, 96, 78
    row = np.floor(yy / fh)
    fx = (xx + (row % 2) * fw / 2) % fw - fw / 2
    fy = yy % fh - fh                       # the fan's middle is at the bottom of its cell
    r = np.sqrt(fx * fx + fy * fy)
    angle = np.degrees(np.arctan2(-fy, fx))
    inFan = r < radius
    arcs = np.zeros_like(r)
    for ar in (26, 50, 76):
        arcs = np.maximum(arcs, np.clip(1.4 - np.abs(r - ar), 0, 1))
    rays = np.clip(1.3 - np.abs(((angle + 7.5) % 15) - 7.5) * r * math.pi / 180, 0, 1) * (r > 26) * (r < 76)
    return np.maximum(arcs * (r < radius + 2), rays * inFan)


# The wall, the mantelpiece, and the case (all but the round dial and its bezel)
def drawBackground():
    w, h = scr.SCREEN_WIDTH, scr.SCREEN_HEIGHT
    xx, yy = screenGrid(w, h)
    rng = np.random.default_rng(31)

    lines = wallpaper(xx, yy)
    rgb = np.array(WALL, np.float32) * (0.9 + 0.05 * waves(xx, yy, 5, 200, rng))[..., None]
    rgb = rgb * (1 - 0.45 * lines[..., None]) + np.array(GOLD, np.float32) * (0.45 * lines)[..., None]
    rgb *= (1.08 - 0.3 * smoothstep(0, w + h, xx + yy))[..., None]

    # the case's shadow on the wall
    d = caseDistance(xx - 34, yy - 26)
    rgb *= (1 - 0.65 * (1 - smoothstep(-30, 60, d)))[..., None]

    # the mantelpiece: white marble with grey veins, its top catching the light
    wander = waves(xx, yy * 3, 6, 160, rng) + 0.35 * waves(xx, yy * 3, 6, 30, rng)
    veins = np.exp(-np.abs(np.sin(wander * 2.2)) * 22) + 0.5 * np.exp(-np.abs(np.sin(wander * 5.1 + 1)) * 30)
    cloud = 0.04 * waves(xx, yy * 2, 6, 90, rng)
    marble = (np.array(MARBLE, np.float32) + (np.array(VEIN, np.float32) - MARBLE) * (0.45 * veins)[..., None]) * (1 + cloud)[..., None]
    top = (yy >= MANTEL_Y) & (yy < MANTEL_Y + 34)
    front = yy >= MANTEL_Y + 34
    shelf = np.where(top[..., None], marble * 1.0, marble * 0.78)
    shelf *= (1 - 0.35 * smoothstep(MANTEL_Y + 40, h, yy))[..., None]
    edge = np.exp(-((yy - MANTEL_Y - 34) / 1.6) ** 2)
    shelf += (60 * edge)[..., None]
    # the clock's shadow on the shelf, and the shelf's on the wall just above it
    onShelf = np.abs(xx - CENTRE[0]) - (BLOCKS[-1][0] + 20)
    shelf *= (1 - 0.5 * (1 - smoothstep(-40, 50, onShelf)) * (yy < MANTEL_Y + 30))[..., None]
    rgb = np.where((top | front)[..., None], shelf, rgb)

    # the black lacquer case: rounded at its edges, with a hard shine
    d = caseDistance(xx, yy)
    inside = np.clip(0.5 - d, 0, 1)
    nx, ny, nz = bevel(-d, 16)
    diffuse, specular = lighting(nx, ny, nz, 40)
    sheen = 22 * np.exp(-(((xx - CENTRE[0] + 260) / 260) ** 2 + ((yy - 300) / 340) ** 2))
    lacquer = np.array(LACQUER, np.float32) * (0.5 + 0.9 * diffuse)[..., None] + (230 * specular + sheen)[..., None]
    rgb = rgb * (1 - inside[..., None]) + lacquer * inside[..., None]

    # the chrome strip, and the speed lines across the case
    cx = CENTRE[0]
    for half, top, bottom, corner, isChrome in BLOCKS:
        if isChrome:
            chromeOver(rgb, xx, yy, cx, (top + bottom) / 2, half, (bottom - top) / 2, corner, 7)
    for y in SPEED_LINES:
        chromeOver(rgb, xx, yy, cx, y, SPEED_LINE_HALF, 4, 4, 4)

    return toSurface(vignette(rgb, xx, yy, 0.35))


# A rounded rectangle of chrome laid over the picture (only the part of it round the
# rectangle is worked on), its edges rounded over `width` pixels
def chromeOver(rgb, xx, yy, cx, cy, halfW, halfH, corner, width):
    area = (slice(max(0, int(cy - halfH - 2)), int(cy + halfH + 3)), slice(max(0, int(cx - halfW - 2)), int(cx + halfW + 3)))
    d = roundedBox(xx[area], yy[area], cx, cy, halfW, halfH, corner)
    inside = np.clip(0.5 - d, 0, 1)
    nx, ny, nz = bevel(-d, width)
    colour = np.array(CHROME, np.float32) * chrome(nx, ny, nz)[..., None]
    rgb[area] = rgb[area] * (1 - inside[..., None]) + colour * inside[..., None]


# The stepped chrome bezel and the sunburst dial, with its numerals, 2 * RADIUS across
def drawDial():
    size = 2 * RADIUS
    r, ux, uy, dx, dy = polarGrid(size)
    rng = np.random.default_rng(37)

    # the bezel: three steps, each higher than the one inside it, with rounded tops
    rs = np.linspace(0, RADIUS + 2, 3000)
    hs = np.zeros_like(rs)
    for inner, outer, height in ((DIAL_RADIUS, 350, 6), (350, 373, 13), (373, 396, 22)):
        band = (rs >= inner) & (rs < outer)
        hs[band] = height + 3.5 * np.sin(math.pi * (rs[band] - inner) / (outer - inner))
    hs = np.convolve(hs, np.ones(9) / 9, "same")
    slope = np.interp(r, rs, np.gradient(hs, rs))
    nx, ny, nz = -slope * ux, -slope * uy, np.ones_like(r)
    length = np.sqrt(nx * nx + ny * ny + nz * nz)
    nx, ny, nz = nx / length, ny / length, nz / length
    bezelRgb = np.array(CHROME, np.float32) * chrome(nx, ny, nz)[..., None]
    _, specular = lighting(nx, ny, nz, 80)
    bezelRgb += (200 * specular)[..., None]

    # the dial: brushed out from the middle, so the light catches it in a wide cross
    angle = np.arctan2(dy, dx)
    lightAngle = math.atan2(LIGHT[1], LIGHT[0])
    sunburst = 0.86 + 0.13 * np.cos(2 * (angle - lightAngle)) + 0.035 * np.sin(angle * 900 + rng.uniform(0, 6)) * rng.uniform(0.5, 1, r.shape)
    inner = r < 0.5 * DIAL_RADIUS           # inside the inner ring, turned in fine circles instead
    sunburst = np.where(inner, 0.93 + 0.03 * np.sin(r * 1.3) + 0.05 * np.cos(angle - lightAngle) * r / DIAL_RADIUS, sunburst)
    dialRgb = np.array(CHAMPAGNE, np.float32) * sunburst[..., None]

    # the bezel's shadow on the dial
    shift = 9
    sr = np.sqrt((dx + LIGHT[0] * shift) ** 2 + (dy + LIGHT[1] * shift) ** 2)
    dialRgb *= (1 - 0.45 * smoothstep(DIAL_RADIUS - 22, DIAL_RADIUS + 2, sr))[..., None]

    inDial = np.clip(DIAL_RADIUS + 0.5 - r, 0, 1)[..., None]
    rgb = dialRgb * inDial + bezelRgb * (1 - inDial)
    alpha = np.clip(396 - r, 0, 1) * 255
    dial = toSurface(rgb, alpha)
    dial.blit(drawMarks(), (0, 0))
    return dial


# The minute track, with a little diamond at each five minutes, the rings, and the numerals
def drawMarks():
    big = 2 * RADIUS * SS
    c = RADIUS * SS
    marks = pygame.Surface((big, big), pygame.SRCALPHA)
    marks.fill((*INK, 0))
    D = DIAL_RADIUS

    def point(radius, angle):
        a = math.radians(angle)
        return c + radius * SS * math.sin(a), c - radius * SS * math.cos(a)

    def ring(radius, width):
        pygame.draw.circle(marks, INK, (c, c), round(radius * SS), round(width * SS))

    outer, inner = 0.94 * D, 0.875 * D
    ring(outer, 1.6)
    ring(inner, 1.2)
    for minute in range(60):
        a = minute * 6
        if minute % 5:
            pygame.draw.line(marks, INK, point(inner, a), point(outer, a), round(1.4 * SS))
        else:
            mid, half, wide = (inner + outer) / 2, (outer - inner) / 2 + 3, 1.6
            pygame.draw.polygon(marks, INK, [point(mid - half, a), point(mid, a - wide), point(mid + half, a), point(mid, a + wide)])

    ring(0.5 * D, 1.6)
    ring(0.478 * D, 0.8)

    font = decoFont(round(0.2 * D * SS))
    for hour in range(1, 13):
        x, y = point(0.69 * D, hour * 30)
        blitText(marks, font, str(hour), INK, x, y)

    return pygame.transform.smoothscale(marks, (2 * RADIUS, 2 * RADIUS))


# Lozenge hands, and a fine seconds hand with a diamond at its tail
def makeHands():
    D = DIAL_RADIUS
    L = 0.56 * D
    hour = makeHand(L, 0.16 * L, 0.09 * L, [
        taper(-0.16 * L, 0.38 * L, 11, 8),
        ("disc", -0.16 * L, 9),
        ("poly", [(0, 0.3 * L), (0.085 * L, 0.56 * L), (0, L), (-0.085 * L, 0.56 * L)]),
        ("hole", 0.56 * L, 4),
        ("disc", 0, 15),
    ], (5, 7), HAND, HAND_LIGHT)

    L = 0.86 * D
    minute = makeHand(L, 0.12 * L, 0.05 * L, [
        taper(-0.12 * L, 0.48 * L, 9, 6),
        ("disc", -0.12 * L, 7),
        ("poly", [(0, 0.4 * L), (0.048 * L, 0.64 * L), (0, L), (-0.048 * L, 0.64 * L)]),
        ("hole", 0.64 * L, 3.5),
        ("disc", 0, 12),
    ], (7, 10), HAND, HAND_LIGHT)

    L = 0.9 * D
    second = makeHand(L, 0.27 * L, 9, [
        taper(-0.2 * L, L, 3.5, 1.5),
        ("poly", [(0, -0.09 * L), (7.5, -0.18 * L), (0, -0.27 * L), (-7.5, -0.18 * L)]),
        ("disc", 0, 7),
    ], (9, 12), HAND, HAND_LIGHT)

    return hour, minute, second


##==================================================================
## THE FACE
##==================================================================

class DecoFace(AnalogueFace):

    name = "DECO"
    centre = CENTRE
    radius = RADIUS
    statusColour = GOLD

    def build(self, chimeVolume, tickVolume):
        self.background = drawBackground()
        self.dial = drawDial()
        self.hands = makeHands()
        self.nut = dome(9, (205, 208, 214))
        self.glass = drawGlass(RADIUS, DIAL_RADIUS, strength=0.8)
        self.chimes, self.gong, self.ticks = makeChimes(chimeVolume, tickVolume)

    def sounds(self):
        return list(self.chimes.values()) + [self.gong] + self.ticks

    def tickSounds(self):
        return self.ticks

    # The seconds hand moves BEATS times a second, settling after each
    def angles(self, now):
        hours, minutes, _ = super().angles(now)
        seconds = now.second + now.microsecond / 1e6
        beat = math.floor(seconds * BEATS)
        fraction = seconds * BEATS - beat
        return hours, minutes, (beat - 1 + settle(fraction, 0.12)) / BEATS * 6

    def chime(self, hour, minute):
        quarter = minute // 15
        sounds = [(0, self.chimes[quarter])]
        if quarter == 0 and STRIKE_HOURS:
            first = 3 * PAIR_SECONDS + DONG_AFTER + STRIKE_DELAY
            sounds += [(first + i * STRIKE_GAP, self.gong) for i in range(hour % 12 or 12)]
        return sounds

    # A tick each time the seconds hand moves, tick and tock in turn
    beats = BEATS

    def beatSound(self, now, beat):
        return self.ticks[(now.second * BEATS + beat) % 2]
