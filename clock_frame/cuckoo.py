"""
cuckoo.py

A Black Forest cuckoo clock hanging on a knotty pine wall: a little carved house with a
shingled roof, a dark wooden dial with bone hands and numerals, two windows with geraniums in
their boxes, a pendulum with a carved leaf swinging below, and two pine-cone weights on their
chains. The weights go down through the day (the left one only as the cuckoo calls) until
they are wound up again at CUCKOO_WIND_HOUR.

On the hour the little doors under the roof fly open and the cuckoo comes out, bowing and
lifting its wings and tail as it calls, once for each hour; at half past it calls once. Its
call is two small wooden pipes, blown by bellows, a third apart. The clock ticks, tock-tock,
once a second (CUCKOO_BEATS), in time with the pendulum.
"""

import datetime
import math
import time
from types import SimpleNamespace
import pygame
import numpy as np
import screens as scr
import synth
from .common import (AnalogueFace, Hand, SS, LIGHT, polarGrid, screenGrid, smoothstep, waves,
                     toSurface, lighting, bevel, roundedBox, vignette, dome, blitText, sysFont,
                     makeHand, makeShadow, taper, tickStroke, mixNotes, makeSound, SERIF_FONTS)

##==================================================================
## SETTINGS (they are in settings.py, next to lcars.py)
##==================================================================

from settings import (
    CUCKOO_BEATS as BEATS,
    CUCKOO_SWING as SWING,
    CUCKOO_WIND_HOUR as WIND_HOUR,
    CUCKOO_HALF_HOUR as HALF_HOUR,
    CUCKOO_CALL_GAP as CALL_GAP,
    CUCKOO_CENTRE_X as CX,
    CUCKOO_APEX_Y as APEX_Y,
    CUCKOO_ROOF_SLOPE as ROOF_SLOPE,
    CUCKOO_ROOF_THICKNESS as ROOF_THICKNESS,
    CUCKOO_ROOF_HALF as ROOF_HALF,
    CUCKOO_WALL_HALF as WALL_HALF,
    CUCKOO_BASE_Y as BASE_Y,
    CUCKOO_DIAL_Y as DIAL_Y,
    CUCKOO_DIAL_RADIUS as DIAL_RADIUS,
    CUCKOO_DOOR_TOP as DOOR_TOP,
    CUCKOO_DOOR_HALF as DOOR_HALF,
    CUCKOO_DOOR_HEIGHT as DOOR_HEIGHT,
    CUCKOO_WINDOW_X as WINDOW_X,
    CUCKOO_WINDOW_Y as WINDOW_Y,
    CUCKOO_PENDULUM_LENGTH as PENDULUM_LENGTH,
    CUCKOO_WEIGHT_X as WEIGHT_X,
    CUCKOO_WEIGHT_HIGHEST as WEIGHT_HIGHEST,
    CUCKOO_WEIGHT_LOWEST as WEIGHT_LOWEST,
    CUCKOO_PINE as PINE,
    CUCKOO_WOOD as WOOD,
    CUCKOO_TRIM as TRIM,
    CUCKOO_ROOF as ROOF,
    CUCKOO_DIAL as DIAL,
    CUCKOO_BONE as BONE,
    CUCKOO_BONE_LIGHT as BONE_LIGHT,
    CUCKOO_IRON as IRON,
    CUCKOO_CHAIN as CHAIN,
    CUCKOO_BIRD as BIRD,
    CUCKOO_BIRD_DARK as BIRD_DARK,
    CUCKOO_BIRD_BREAST as BIRD_BREAST,
    CUCKOO_BEAK as BEAK,
    CUCKOO_TEXT_COLOUR as TEXT_COLOUR,
)

N = math.hypot(1, ROOF_SLOPE)       # divides a height across the roof to make it a distance square to it
DOOR_BOTTOM = DOOR_TOP + DOOR_HEIGHT
BASE_TOP = BASE_Y - 44              # the carved board along the bottom of the house...
BASE_HALF = WALL_HALF + 28          # ...a little wider than the house
SCALLOP = 14                        # how far the carved trim hangs below the roof and the base
DIAL_INNER = 0.86 * DIAL_RADIUS     # inside the carved ring
PIVOT_Y = BASE_Y - 90               # where the pendulum hangs from, inside the house
CLIP_Y = BASE_Y + SCALLOP           # the pendulum is seen only below the house
CONE_W, CONE_H, HOOK_H = 64, 170, 22    # a pine-cone weight, and the ring on its top
CHAIN_W, CHAIN_H = 16, 400


##==================================================================
## THE SOUNDS
##==================================================================

CU, KOO = 880.00, 739.99        # A and F sharp: the two pipes, a minor third apart
CU_TO_KOO = 0.28                # seconds from the "cu" to the "koo"...
CU_SECONDS, KOO_SECONDS = 0.16, 0.3     # ...and how long each lasts

# When things happen, in seconds from the moment the show begins (the gears whirr first)
DOOR_START = 0.4                # the doors fly open...
DOOR_SWING = 0.2
OUT_START = 0.5                 # ...the bird comes out...
OUT_MOVE = 0.3
FIRST_CALL = 1.1                # ...and calls, every CALL_GAP seconds
STAY = 1.0                      # after the last call starts, before it goes back in...
GO_IN = 0.3                     # ...which takes this long...
DOORS_SHUT = 0.44               # ...and the doors are shut this long after it starts to


# One note of a small stopped wooden pipe, blown by a bellows that falls as it empties, so the
# note sags a little at the end; with a puff of breath as it starts
def pipe(frequency, seconds, seed):
    t = synth.times(seconds)
    rng = np.random.default_rng(seed)
    pressure = (1 - np.exp(-t / 0.02)) * (0.6 + 0.4 * np.exp(-t / 0.2))
    pressure *= np.clip((seconds - t) / 0.04, 0, 1)
    f = frequency * (0.985 + 0.015 * pressure)
    phase = 2 * math.pi * np.cumsum(f) / synth.SAMPLE_RATE
    tone = np.sin(phase) + 0.16 * np.sin(3 * phase) + 0.05 * np.sin(5 * phase)
    breath = synth.noise(seconds, rng)
    breath = synth.smooth(breath, 3) - synth.smooth(breath, 30)
    chiff = breath * np.exp(-t / 0.025) * np.minimum(1.0, t / 0.002)
    sound = pressure * (tone + 0.12 * breath) + 0.5 * chiff
    return sound / np.max(np.abs(sound))


# "Cu-koo", with the knock of each bellows' lid as it is let fall
def makeCall(volume):
    cu, koo = pipe(CU, CU_SECONDS, 71), pipe(KOO, KOO_SECONDS, 72)
    knock = tickStroke(0.5, 0.01, 0.0, case=2.0)
    return makeSound(mixNotes([(0, cu, 1.0, 0.5), (CU_TO_KOO, koo, 1.0, 0.5),
                               (0, knock, 0.2, 0.5), (CU_TO_KOO, knock, 0.2, 0.5)]), volume)


# The gears running as the cuckoo's train is let go: a quick rattle of clicks
def makeWhirr(volume):
    t = synth.times(0.6)
    rng = np.random.default_rng(73)
    sound = np.zeros_like(t)
    for i in range(16):
        tt = t - (i * 0.024 + rng.uniform(0, 0.004))
        on = tt >= 0
        tt = np.where(on, tt, 0)
        click = rng.uniform(-1, 1, len(t)) * np.exp(-tt / 0.0012) + 0.6 * np.sin(2 * math.pi * 2600 * tt) * np.exp(-tt / 0.003)
        sound += (1 - i / 20) * click * on
    sound *= np.minimum(1.0, (t[-1] - t) / 0.02)
    return makeSound(sound / np.max(np.abs(sound)), volume)


# The tick of the brass movement: a sharp click as the pallet meets the escape wheel, with a
# brief high ring of the metal and none of the case, then the tooth dropping a moment later.
# pitch scales the ring, so that the tock can be a little lower than the tick.
TICK_METAL = [(2400, 0.55, 0.0030), (3700, 0.4, 0.0020), (5300, 0.25, 0.0012)]    # (Hz, loudness, seconds to die away)

def metalTick(pitch, seed):
    t = synth.times(0.04)
    rng = np.random.default_rng(seed)
    sound = np.zeros_like(t)
    for at, loudness in ((0.0, 1.0), (0.004, 0.5)):
        tt = np.maximum(t - at, 0)
        on = t >= at
        click = synth.noise(0.04, rng)
        click = click - synth.smooth(click, 4)              # only the hiss of it: no thud
        part = 0.8 * click * np.exp(-tt / 0.0005)
        for f, amp, decay in TICK_METAL:
            part += amp * np.sin(2 * math.pi * f * pitch * tt + rng.uniform(0, 6.3)) * np.exp(-tt / decay)
        sound += loudness * part * on * np.minimum(1.0, tt / 0.0002)
    sound *= np.minimum(1.0, (t[-1] - t) / 0.005)
    return sound / np.max(np.abs(sound))


def makeSounds(chimeVolume, tickVolume):
    call = makeCall(chimeVolume)
    whirr = makeWhirr(chimeVolume * 0.25)
    clack = makeSound(tickStroke(1.25, 0.004, 0.3, case=0.7), chimeVolume * 0.4)     # the doors
    ticks = [makeSound(metalTick(1.0, 81), tickVolume * 0.8),
             makeSound(metalTick(0.9, 82), tickVolume * 0.75)]
    return call, whirr, clack, ticks


# How many times it calls at hour:minute
def callsAt(hour, minute):
    if minute == 0:
        return hour % 12 or 12
    return 1 if minute == 30 and HALF_HOUR else 0


# Not a sound, but played with the calls, as though it were one, so that the bird comes out
# with them: whenever they are played (on the hour, or again with the OK button held down),
# and goes back in when they are stopped
class Cue:

    def __init__(self, face, count):
        self.face = face
        self.count = count

    def play(self):
        self.face.startShow(self.count)

    def stop(self):
        self.face.endShow()

    def get_num_channels(self):
        return 1 if self.face.show else 0


##==================================================================
## DRAWING HELPERS
##==================================================================

# The light on a surface whose height at each pixel is given
def heightLight(height, shininess=30):
    gy, gx = np.gradient(height)
    length = np.sqrt(gx * gx + gy * gy + 1)
    return lighting(-gx / length, -gy / length, 1 / length, shininess)


# Light and dark streaks of wood grain, running up and down (or across)
def woodGrain(xx, yy, rng, vertical=True):
    a, b = (xx, yy) if vertical else (yy, xx)       # a is across the grain
    rows = np.convolve(rng.normal(0, 1, 4096), [0.25, 0.5, 0.25], "same")
    position = (a + 5 * waves(a * 0.3, b * 0.05, 4, 30, rng)) % 4096
    streaks = np.interp(position, np.arange(4096), rows)
    return 0.9 + 0.06 * streaks + 0.05 * waves(a * 2, b * 0.15, 4, 60, rng)


# Carved wood, given how far each pixel is from its edge (minus inside), rounded over `width`
def carved(d, colour, width, xx, yy, rng, vertical=True):
    nx, ny, nz = bevel(-d, width)
    diffuse, specular = lighting(nx, ny, nz, 30)
    grain = woodGrain(xx, yy, rng, vertical)
    return np.array(colour, np.float32) * (grain * (0.45 + 0.7 * diffuse))[..., None] + (70 * specular)[..., None]


def fract(x):
    return x - np.floor(x)


##==================================================================
## THE HOUSE
##==================================================================

# How far each pixel is from the edge of each part of the house (minus inside)
def roofDistance(xx, yy):
    ax = np.abs(xx - CX)
    outer = (APEX_Y + ax * ROOF_SLOPE - yy) / N
    inner = (yy - APEX_Y - ROOF_THICKNESS - ax * ROOF_SLOPE) / N
    return np.maximum(np.maximum(outer, inner), ax - ROOF_HALF)


def wallDistance(xx, yy):
    ax = np.abs(xx - CX)
    return np.maximum.reduce([ax - WALL_HALF, (APEX_Y + 0.6 * ROOF_THICKNESS + ax * ROOF_SLOPE - yy) / N, yy - BASE_TOP - 4])


def baseDistance(xx, yy):
    return roundedBox(xx, yy, CX, (BASE_TOP + BASE_Y) / 2, BASE_HALF, (BASE_Y - BASE_TOP) / 2, 6)


def houseDistance(xx, yy):
    return np.minimum.reduce([roofDistance(xx, yy), wallDistance(xx, yy), baseDistance(xx, yy)])


# The cuckoo's doorway, round at the top (grow makes it bigger all round, for its frame)
def doorDistance(dx, yy, grow=0):
    hw = DOOR_HALF + grow
    cy = DOOR_TOP + DOOR_HALF
    rect = np.maximum(np.maximum(np.abs(dx) - hw, cy - yy), yy - (DOOR_BOTTOM + grow))
    return np.minimum(rect, np.hypot(dx, yy - cy) - hw)


# The roof's shingles, in rows along its slopes, each rounded at the bottom
def shingles(xx, yy, rng):
    dx = xx - CX
    ax = np.abs(dx)
    along = (ax + (yy - APEX_Y) * ROOF_SLOPE) / N
    down = (yy - APEX_Y - ax * ROOF_SLOPE) / N
    rowH = ROOF_THICKNESS / N / 4
    row = np.floor(down / rowH)
    fy = down / rowH - row
    col = along / 30 + 0.5 * row
    tile = np.floor(col)
    fx = col - tile - 0.5
    tone = 0.85 + 0.25 * fract(np.sin(row * 12.9898 + tile * 78.233 + (dx < 0) * 3.1) * 43758.5453)
    tip = 1 - 0.3 * (2 * fx) ** 2
    shade = (0.6 + 0.4 * smoothstep(0, 0.4, fy)) * np.where(fy > tip, 0.45, 1.0) * np.where(np.abs(fx) > 0.47, 0.5, 1.0)
    side = np.where(dx < 0, 1.08, 0.86)         # the left slope faces the light
    grain = 1 + 0.06 * waves(along * 0.3, down * 3, 3, 10, rng)
    return np.array(ROOF, np.float32) * (tone * shade * side * grain)[..., None]


# A little window with four panes, and a box of red geraniums under it
def drawWindow():
    w, h = 96, 136
    big = pygame.Surface((w * SS, h * SS), pygame.SRCALPHA)
    big.fill((0, 0, 0, 0))

    def box(x, y, bw, bh):
        return pygame.Rect(round(x * SS), round(y * SS), round(bw * SS), round(bh * SS))

    dark = tuple(int(c * 0.5) for c in TRIM)
    fx, fy, fw, fh = 11, 4, 74, 100
    pygame.draw.rect(big, dark, box(fx - 1, fy - 1, fw + 2, fh + 2), border_radius=3 * SS)
    pygame.draw.rect(big, TRIM, box(fx, fy, fw, fh), border_radius=3 * SS)

    # the glass, the sky reflected in it at the top, dark below
    gx, gy, gw, gh = fx + 8, fy + 8, fw - 16, fh - 16
    for i in range(gh * SS):
        k = i / (gh * SS)
        colour = [round(a + (b - a) * k) for a, b in zip((92, 118, 140), (20, 26, 34))]
        pygame.draw.line(big, colour, (gx * SS, gy * SS + i), ((gx + gw) * SS - 1, gy * SS + i))
    pygame.draw.polygon(big, (110, 136, 156), [((gx + 6) * SS, (gy + gh) * SS), ((gx + 30) * SS, gy * SS),
                                               ((gx + 40) * SS, gy * SS), ((gx + 16) * SS, (gy + gh) * SS)])
    pygame.draw.rect(big, TRIM, box(fx + fw / 2 - 2.5, gy, 5, gh))
    pygame.draw.rect(big, TRIM, box(gx, gy + gh / 2 - 2.5, gw, 5))
    pygame.draw.rect(big, dark, box(gx, gy, gw, gh), max(1, SS))

    # the flower box, and the geraniums in it
    bx, by, bw, bh = 2, fy + fh + 4, 92, 22
    rng = np.random.default_rng(5)
    for _ in range(16):
        x, y = rng.uniform(bx + 6, bx + bw - 6), by - rng.uniform(0, 9)
        green = (46, 92, 40) if rng.random() < 0.5 else (64, 116, 50)
        pygame.draw.circle(big, green, (x * SS, y * SS), rng.uniform(5, 7.5) * SS)
    for _ in range(6):
        cx, cy = rng.uniform(bx + 10, bx + bw - 10), by - rng.uniform(9, 16)
        for _ in range(6):
            red = (196, 30, 36) if rng.random() < 0.6 else (232, 74, 70)
            pygame.draw.circle(big, red, ((cx + rng.uniform(-5, 5)) * SS, (cy + rng.uniform(-4, 4)) * SS), rng.uniform(2.4, 3.6) * SS)
    pygame.draw.rect(big, (40, 22, 12), box(bx - 1, by - 1, bw + 2, bh + 2), border_radius=2 * SS)
    pygame.draw.rect(big, (128, 74, 40), box(bx, by, bw, bh), border_radius=2 * SS)
    pygame.draw.line(big, (96, 54, 28), (bx * SS, (by + bh / 2) * SS), ((bx + bw) * SS, (by + bh / 2) * SS), SS)

    return pygame.transform.smoothscale(big, (w, h))


# The house, without its dial: the front, the doorway, the roof, the carved trim and the base.
# Returns its picture and where its left edge is on the screen (its top is at the top).
def drawHouse():
    x0 = CX - ROOF_HALF - 6
    w, h = 2 * (ROOF_HALF + 6), BASE_Y + SCALLOP + 4
    xx, yy = screenGrid(w, h)
    xx = xx + x0
    dx = xx - CX
    ax = np.abs(dx)
    rng = np.random.default_rng(41)
    rgb = np.zeros((h, w, 3), np.float32)
    alpha = np.zeros((h, w), np.float32)

    def lay(d, colour):
        inside = np.clip(0.5 - d, 0, 1)
        rgb[:] = rgb * (1 - inside[..., None]) + colour * inside[..., None]
        alpha[:] = np.maximum(alpha, inside)

    # --- the front: dark boards standing side by side, with grooves between them
    wallD = wallDistance(xx, yy)
    bx = (dx + 23) % 46
    board = np.floor((dx + 23) / 46).astype(int)
    tone = rng.uniform(0.86, 1.1, 64)[board % 64]
    grooves = np.exp(-(bx / 1.6) ** 2) + np.exp(-((bx - 46) / 1.6) ** 2)
    diffuse, specular = heightLight(5 * smoothstep(0, 6, -wallD) - 2.5 * grooves)
    wall = np.array(WOOD, np.float32) * (tone * woodGrain(xx, yy, rng) * (0.5 + 0.65 * diffuse))[..., None] + (50 * specular)[..., None]

    # the shadows on it of the roof, the dial, the windows and the doorway's frame
    inner = APEX_Y + ROOF_THICKNESS + ax * ROOF_SLOPE
    wall *= (1 - 0.55 * (1 - smoothstep(SCALLOP * 0.5, SCALLOP + 34, yy - inner)))[..., None]
    wall *= (1 - 0.6 * (1 - smoothstep(DIAL_RADIUS - 14, DIAL_RADIUS + 20, np.hypot(dx - 9, yy - DIAL_Y - 13))))[..., None]
    for side in (-1, 1):
        d = roundedBox(xx, yy, CX + side * WINDOW_X + 6, WINDOW_Y + 22, 47, 68, 6)
        wall *= (1 - 0.45 * (1 - smoothstep(-8, 14, d)))[..., None]
    wall *= (1 - 0.45 * (1 - smoothstep(-4, 12, doorDistance(dx - 5, yy - 7, 9))))[..., None]
    lay(wallD, wall)

    # --- the cuckoo's doorway: a carved frame, dark inside, with a little perch below it
    frameD = doorDistance(dx, yy, 9)
    lay(frameD, carved(frameD, TRIM, 5, xx, yy, rng))
    inside = np.array((22, 13, 8), np.float32) * (0.6 + 0.6 * smoothstep(DOOR_TOP, DOOR_BOTTOM, yy))[..., None]
    lay(doorDistance(dx, yy), inside)
    perchD = roundedBox(xx, yy, CX, DOOR_BOTTOM + 6, DOOR_HALF + 18, 6, 3)
    lay(perchD, carved(perchD, TRIM, 4, xx, yy, rng, vertical=False))

    # --- the roof, and the carved scallops hanging under its edge
    roofD = roofDistance(xx, yy)
    nx, ny, nz = bevel(-roofD, 6)
    diffuse, specular = lighting(nx, ny, nz, 30)
    lay(roofD, shingles(xx, yy, rng) * (0.55 + 0.6 * diffuse)[..., None] + (50 * specular)[..., None])

    along = (ax + (yy - APEX_Y) * ROOF_SLOPE) / N
    below = (yy - inner) / N
    sx = (along % 26) / 26 - 0.5
    scallopD = np.maximum.reduce([-(below + 2), below - SCALLOP * np.sqrt(np.clip(1 - (2 * sx) ** 2, 0, 1)),
                                  ax - (ROOF_HALF - 10), 2.5 - np.hypot(sx * 26, below - SCALLOP * 0.45)])
    lay(scallopD, carved(scallopD, TRIM, 3, xx, yy, rng))

    # --- the base, with a groove along it, and scallops under it too
    baseD = baseDistance(xx, yy)
    base = carved(baseD, TRIM, 6, xx, yy, rng, vertical=False)
    base *= (1 - 0.4 * np.exp(-((yy - (BASE_TOP + BASE_Y) / 2) / 1.5) ** 2))[..., None]
    lay(baseD, base)

    below = yy - BASE_Y
    sx = (dx % 24) / 24 - 0.5
    scallopD = np.maximum.reduce([-(below + 2), below - SCALLOP * np.sqrt(np.clip(1 - (2 * sx) ** 2, 0, 1)),
                                  ax - (BASE_HALF - 8)])
    lay(scallopD, carved(scallopD, TRIM, 3, xx, yy, rng))

    house = toSurface(rgb, alpha * 255)
    window = drawWindow()
    for side in (-1, 1):
        house.blit(window, window.get_rect(midtop=(CX + side * WINDOW_X - x0, WINDOW_Y - 54)))
    finial = dome(11, TRIM)
    house.blit(finial, finial.get_rect(center=(CX - x0, APEX_Y + 2)))
    return house, x0


# The knotty pine boards of the wall, with the house's shadow on them
def drawWall():
    w, h = scr.SCREEN_WIDTH, scr.SCREEN_HEIGHT
    xx, yy = screenGrid(w, h)
    rng = np.random.default_rng(43)

    boardW = 150
    board = np.floor((xx + 37) / boardW)
    bx = (xx + 37) % boardW
    tone = rng.uniform(0.86, 1.1, 64)[board.astype(int) % 64]
    grain = woodGrain(xx + board * 53, yy, rng)
    rgb = np.array(PINE, np.float32) * (tone * grain * (0.95 + 0.05 * waves(xx, yy, 4, 300, rng)))[..., None]

    # the knots, each in a darker ring
    for _ in range(14):
        kx, ky = rng.uniform(0, w), rng.uniform(0, h)
        area = (slice(max(0, int(ky - 40)), int(ky + 40)), slice(max(0, int(kx - 30)), int(kx + 30)))
        r = np.hypot(xx[area] - kx, (yy[area] - ky) / 1.5)
        rgb[area] *= (1 - 0.55 * np.exp(-(r / 6) ** 2) - 0.2 * np.exp(-((r - 12) / 4) ** 2))[..., None]

    # the gaps between the boards, with the light catching the edge beside each
    gap = np.exp(-(bx / 1.3) ** 2) + np.exp(-((bx - boardW) / 1.3) ** 2)
    rgb *= (1 - 0.6 * gap + 0.1 * np.exp(-((bx - 3) / 1.5) ** 2))[..., None]

    rgb *= (1 - 0.6 * (1 - smoothstep(-20, 50, houseDistance(xx - 26, yy - 32))))[..., None]
    return toSurface(vignette(rgb, xx, yy, 0.4))


##==================================================================
## THE DIAL AND THE HANDS
##==================================================================

# Dark wood in a ring carved into beads, 2 * DIAL_RADIUS across
def drawDial():
    R = DIAL_RADIUS
    size = 2 * R
    r, ux, uy, dx, dy = polarGrid(size)
    rng = np.random.default_rng(47)
    angle = np.arctan2(dy, dx)

    mid, half = (DIAL_INNER + R) / 2, (R - DIAL_INNER) / 2
    profile = np.sqrt(np.clip(1 - ((r - mid) / half) ** 2, 0, None)) * half * 0.6
    diffuse, specular = heightLight(profile * (0.8 + 0.2 * np.abs(np.cos(angle * 30))), 25)
    ringRgb = np.array(TRIM, np.float32) * (woodGrain(dx + R, dy + R, rng) * (0.4 + 0.75 * diffuse))[..., None] + (60 * specular)[..., None]

    dialRgb = np.array(DIAL, np.float32) * (woodGrain(dx + R, dy + R, rng, vertical=False) * (1 - 0.12 * r / R))[..., None]
    shift = 6
    sr = np.sqrt((dx + LIGHT[0] * shift) ** 2 + (dy + LIGHT[1] * shift) ** 2)
    dialRgb *= (1 - 0.5 * smoothstep(DIAL_INNER - 16, DIAL_INNER + 2, sr))[..., None]

    inDial = np.clip(DIAL_INNER + 0.5 - r, 0, 1)[..., None]
    rgb = dialRgb * inDial + ringRgb * (1 - inDial)
    dial = toSurface(rgb, np.clip(R - 1 - r, 0, 1) * 255)
    dial.blit(drawMarks(), (0, 0))
    return dial


# The minute dots and the numerals, in bone, drawn big and shrunk to make them smooth
def drawMarks():
    R = DIAL_RADIUS
    big = 2 * R * SS
    c = R * SS
    marks = pygame.Surface((big, big), pygame.SRCALPHA)
    marks.fill((*BONE, 0))

    def point(radius, angle):
        a = math.radians(angle)
        return c + radius * SS * math.sin(a), c - radius * SS * math.cos(a)

    track = 0.93 * DIAL_INNER
    for minute in range(60):
        a = minute * 6
        if minute % 5:
            pygame.draw.circle(marks, BONE, point(track, a), 1.8 * SS)
        else:
            pygame.draw.polygon(marks, BONE, [point(track - 7, a), point(track, a - 1.8), point(track + 7, a), point(track, a + 1.8)])

    font = sysFont(SERIF_FONTS, round(0.27 * DIAL_INNER * SS), bold=True)
    for hour in range(1, 13):
        x, y = point(0.74 * DIAL_INNER, hour * 30)
        blitText(marks, font, str(hour), BONE, x, y)

    return pygame.transform.smoothscale(marks, (2 * R, 2 * R))


# Carved bone hands, each with an open ring near its point; it has no seconds hand
class NoHand:
    def draw(self, surface, angle, centre):
        pass


def makeHands():
    k = DIAL_INNER / 160                # the hands' widths grow with the dial
    L = 0.6 * DIAL_INNER
    hour = makeHand(L, 0.22 * L, 18 * k, [
        taper(-0.22 * L, 0.6 * L, 9 * k, 6 * k),
        ("disc", -0.22 * L, 7 * k),
        ("disc", 0.66 * L, 16 * k),
        ("hole", 0.66 * L, 9 * k),
        taper(0.78 * L, L, 10 * k, 0),
        ("disc", 0, 11 * k),
    ], (4, 6), BONE, BONE_LIGHT)

    L = 0.9 * DIAL_INNER
    minute = makeHand(L, 0.18 * L, 12 * k, [
        taper(-0.18 * L, 0.74 * L, 7 * k, 4 * k),
        ("disc", -0.18 * L, 6 * k),
        ("disc", 0.78 * L, 10 * k),
        ("hole", 0.78 * L, 5.5 * k),
        taper(0.82 * L, L, 7 * k, 0),
        ("disc", 0, 9 * k),
    ], (6, 8), BONE, BONE_LIGHT)

    return hour, minute, NoHand()


##==================================================================
## THE PENDULUM, THE WEIGHTS AND THE CHAINS
##==================================================================

# A wooden rod with a carved leaf at its end, hanging from the top middle of its picture
def drawPendulum():
    A, B = 54, 76                       # half the leaf's width and height
    w, h = 2 * A + 12, PENDULUM_LENGTH + B + 8
    xx, yy = screenGrid(w, h)
    x = xx + 0.5 - w / 2
    y = yy + 0.5

    rodD = np.maximum(np.abs(x) - 4, y - PENDULUM_LENGTH)
    ly = y - PENDULUM_LENGTH
    c = (B * B - A * A) / (2 * A)       # the leaf is where two circles overlap, with a wavy edge
    leafD = np.maximum(np.hypot(x - c, ly), np.hypot(x + c, ly)) - (c + A)
    leafD += 2.2 * np.abs(np.sin(np.arctan2(ly, x) * 9))
    leafIn = -leafD

    veins = np.exp(-((((ly - np.abs(x) * 0.7) % 18) - 9) / 1.4) ** 2) * (np.abs(x) > 3) * smoothstep(2, 10, leafIn)
    leafHeight = 7 * smoothstep(0, 12, leafIn) + 2.2 * np.exp(-(x / 2.2) ** 2) - 1.8 * veins + 3
    inLeaf = np.clip(0.5 - leafD, 0, 1)
    inRod = np.clip(0.5 - rodD, 0, 1)
    height = np.where(inLeaf > 0, leafHeight, 3 * smoothstep(0, 4, -rodD))
    diffuse, specular = heightLight(height)

    colour = np.where((inLeaf > 0.01)[..., None], np.array(TRIM, np.float32), np.array(WOOD, np.float32) * 1.2)
    rgb = colour * (0.45 + 0.7 * diffuse)[..., None] + (60 * specular)[..., None]
    return toSurface(rgb, np.maximum(inLeaf, inRod) * 255), pygame.math.Vector2(w / 2, 0)


# A cast iron pine cone, with a ring on top for the chain's hook
def drawWeight():
    w, h = CONE_W + 6, CONE_H + HOOK_H
    xx, yy = screenGrid(w, h)
    x = xx + 0.5 - w / 2
    v = (yy + 0.5 - HOOK_H) / CONE_H        # 0 at the top of the cone, 1 at its tip

    upper = np.sqrt(np.clip(1 - ((0.3 - v) / 0.34) ** 2, 0, 1))
    lower = np.clip(1 - np.clip((v - 0.3) / 0.7, 0, 1) ** 1.7, 0, 1) ** 0.8
    hw = CONE_W / 2 * np.where(v < 0.3, upper, lower) * ((v >= 0) & (v <= 1))

    # its scales, in two spirals, each scale's lower edge standing out
    theta = np.arcsin(np.clip(x / np.maximum(hw, 1e-3), -1, 1))
    fa, fb = fract(theta * 2.6 + v * 11), fract(-theta * 2.6 + v * 11 + 0.5)
    m = np.maximum(fa, fb)
    height = np.sqrt(np.clip(hw * hw - x * x, 0, None)) + 5 * m ** 1.5
    diffuse, specular = heightLight(height, 20)
    rgb = np.array(IRON, np.float32) * ((0.55 + 0.45 * m) * (0.35 + 0.9 * diffuse))[..., None] + (110 * specular)[..., None]
    alpha = np.clip(hw - np.abs(x) + 0.5, 0, 1) * (hw > 0) * 255
    weight = toSurface(rgb, alpha)

    pygame.draw.ellipse(weight, [int(c * 0.8) for c in IRON], (w / 2 - 10, HOOK_H - 5, 20, 9))
    pygame.draw.circle(weight, [int(c * 0.6) for c in IRON], (w / 2, 10), 7, 3)
    pygame.draw.arc(weight, [min(255, int(c * 1.8)) for c in IRON], (w / 2 - 7, 3, 14, 14), 1.6, 3.4, 1)
    return weight


# A long brass chain, its links in turn face on and edge on
def drawChain():
    big = pygame.Surface((CHAIN_W * SS, CHAIN_H * SS), pygame.SRCALPHA)
    big.fill((*CHAIN, 0))
    dark = [int(c * 0.45) for c in CHAIN]
    for i, y in enumerate(range(-6, CHAIN_H, 12)):
        if i % 2 == 0:
            link = pygame.Rect((CHAIN_W / 2 - 6) * SS, y * SS, 12 * SS, 20 * SS)
            pygame.draw.ellipse(big, dark, link, 4 * SS)
            pygame.draw.ellipse(big, CHAIN, link.inflate(-SS, -SS), 2 * SS)
        else:
            link = pygame.Rect((CHAIN_W / 2 - 2) * SS, y * SS, 4 * SS, 20 * SS)
            pygame.draw.rect(big, dark, link, border_radius=2 * SS)
            pygame.draw.rect(big, CHAIN, link.inflate(-2 * SS, -2 * SS), border_radius=SS)
    return pygame.transform.smoothscale(big, (CHAIN_W, CHAIN_H))


# Where the tops of the weights are: the left (the cuckoo's) goes down a little with each call,
# the right (the clock's) steadily, from when they were last wound
def weightTops(now):
    wound = now.replace(hour=WIND_HOUR, minute=0, second=0, microsecond=0)
    if wound > now:
        wound -= datetime.timedelta(days=1)
    going = (now - wound).total_seconds() / 86400

    calls = total = 0
    at = wound + datetime.timedelta(minutes=30)
    for _ in range(48):
        n = callsAt(at.hour, at.minute)
        total += n
        if at <= now:
            calls += n
        at += datetime.timedelta(minutes=30)

    fall = WEIGHT_LOWEST - WEIGHT_HIGHEST
    return round(WEIGHT_HIGHEST + fall * calls / max(1, total)), round(WEIGHT_HIGHEST + fall * going)


##==================================================================
## THE CUCKOO
##==================================================================

BIRD_SIZE = 1.3                     # the bird's drawing below is made this much bigger
BIRD_W, BIRD_H = round(110 * BIRD_SIZE), round(110 * BIRD_SIZE)
BIRD_FEET = (55 * BIRD_SIZE, 106 * BIRD_SIZE)   # where its feet are in its picture


# Turn points about a pivot by deg degrees (clockwise on the screen)
def turn(points, pivot, deg):
    a = math.radians(deg)
    cos, sin = math.cos(a), math.sin(a)
    px, py = pivot
    return [(px + (x - px) * cos - (y - py) * sin, py + (x - px) * sin + (y - py) * cos) for x, y in points]


def ellipse(cx, cy, rx, ry, tilt=0):
    return turn([(cx + rx * math.cos(t), cy + ry * math.sin(t)) for t in np.linspace(0, 2 * math.pi, 48, endpoint=False)], (cx, cy), tilt)


# A blur, averaging over 2r + 1 pixels each way (twice, for a smoother one)
def blur(a, r, passes=2):
    r = max(1, int(r))
    for _ in range(passes):
        for axis in (0, 1):
            pad = [(0, 0), (0, 0)]
            pad[axis] = (r + 1, r)
            c = np.cumsum(np.pad(a, pad, mode="edge"), axis=axis)
            n = a.shape[axis]
            a = (np.take(c, np.arange(2 * r + 1, 2 * r + 1 + n), axis=axis) - np.take(c, np.arange(n), axis=axis)) / (2 * r + 1)
    return a


BS = 2                              # the bird is carved at twice its size, then shrunk


# The rows and columns of a picture where a mask is, and `grow` pixels round them
def bounds(m, grow=0):
    rows, cols = np.flatnonzero(m.any(axis=1)), np.flatnonzero(m.any(axis=0))
    if not len(rows):
        return slice(0, 0), slice(0, 0)
    return slice(max(0, rows[0] - grow), rows[-1] + 1 + grow), slice(max(0, cols[0] - grow), cols[-1] + 1 + grow)

# The poses it is drawn in, (call, beak): bowing, a quarter of the way at a time, then with its
# beak opening (it only opens its beak when it has bowed right down)
POSES = [(i / 4, 0) for i in range(5)] + [(1, 0.5), (1, 1)]

def poseFor(call, beak):
    return (1, round(beak * 2) / 2) if round(beak * 2) else (round(call * 4) / 4, 0)


# The carved, painted cuckoo, facing out of its door, standing with its feet at (0, 0). Each
# part is carved as a rounded lump standing out from what is behind it, with its feathers cut
# into the wings and the tail, then painted and lit from the top left, as the rest of the clock
# is. call (0 to 1) is how far it has bowed as it calls: its head dips, its wings lift out to
# the sides and its tail comes up behind its head. beak is how far its beak is open, the lower
# half dropping below the upper. Returns its picture and its shadow.
def makeBird(call, beak):
    w, h = BIRD_W * BS, BIRD_H * BS
    canvas = pygame.Surface((w, h))
    height = np.zeros((h, w), np.float32)
    rgb = np.zeros((h, w, 3), np.float32)
    alpha = np.zeros((h, w), np.float32)

    k = BIRD_SIZE * BS                  # pixels of the carving for each of the drawing's

    def place(points):
        return [(BIRD_FEET[0] * BS + x * k, BIRD_FEET[1] * BS + y * k) for x, y in points]

    def mask(polygons=(), lines=(), width=1.0):
        canvas.fill((0, 0, 0))
        for points in polygons:
            pygame.draw.polygon(canvas, (255, 255, 255), place(points))
        for points in lines:
            pygame.draw.lines(canvas, (255, 255, 255), False, place(points), max(1, round(width * k)))
        return pygame.surfarray.array_red(canvas).T.astype(np.float32) / 255

    def paint(m, colour, strength=1.0):
        area = bounds(m)
        m = m[area][..., None] * strength
        rgb[area] = rgb[area] * (1 - m) + np.array(colour, np.float32) * m

    # a part `bulge` pixels high in the middle, rounded over `edge` pixels, standing `lift` out
    def carve(polygons, colour, bulge, edge, lift=0.0, lines=(), width=1.0):
        m = mask(polygons, lines, width)
        area = bounds(m, int(edge * k) + 2)
        part = m[area]
        dome = np.sqrt(np.clip(blur(part, edge * k, 1) * 2 - 1, 0, 1))
        height[area] += part * (lift + bulge * dome) * k
        paint(m, colour)
        alpha[area] = np.maximum(alpha[area], part)
        return m

    def mirror(points):
        return [(-x, y) for x, y in points]

    wing = 35 * call                    # degrees each wing lifts out
    dip = 7 * call                      # how far the head comes down
    grow = 1 + 0.08 * call              # and nearer, so a little bigger
    rise = 30 * call                    # how far the tail comes up behind it, fanning out
    gape = 5 * beak                     # how far the lower half of the beak drops

    tail = [(-9, -52), (-9 - 0.8 * rise, -52 - 0.85 * rise), (0, -54 - rise), (9 + 0.8 * rise, -52 - 0.85 * rise), (9, -52)]
    tailMask = carve([tail], BIRD_DARK, 4, 3)
    carve((), BEAK, 1.5, 1, lines=[[(x, -14), (x * 1.1, 0)] for x in (-8, 8)], width=3)        # the legs
    body = carve([ellipse(0, -40, 25, 30)], BIRD, 18, 14, 2)

    # the breast, painted pale with dark bars across it
    paint(blur(mask([ellipse(0, -38, 17, 24)]), k) * body, BIRD_BREAST)
    bars = [[(-half, y - 1.5 - tilt), (0, y), (half, y - 1.5 + tilt)]
            for y, tilt in ((-52, 0.4), (-46.5, -0.3), (-41, 0.5), (-36, -0.2), (-30.5, 0.3), (-25, -0.4))
            for half in [13 * math.sqrt(max(0.0, 1 - ((y + 38) / 24) ** 2))]]
    paint(blur(mask(lines=bars, width=1.0), 1) * body, BIRD_DARK, 0.45)

    leftWing = turn([(-17, -62), (-27, -52), (-31, -34), (-27, -18), (-19, -14), (-15, -30), (-14, -52)], (-17, -60), wing)
    wings = carve([leftWing, mirror(leftWing)], BIRD_DARK, 5, 5, 3)
    neck = carve([ellipse(0, -63 + dip / 2, 13, 9)], BIRD, 5, 5)
    head = carve([ellipse(0, -74 + dip, 17 * grow, 17 * grow)], BIRD, 14, 10)

    # the beak points out at us: the upper half stands right out, and the lower drops below it
    y = -71 + dip
    carve([ellipse(0, y + 6 + gape * 0.5, 4.5 * grow, 0.5 + gape * 0.6)], (110, 28, 18), 0, 1)   # its open mouth
    carve([[(-4.5 * grow, y + 6 + gape), (4.5 * grow, y + 6 + gape), (0, y + 13 + gape)]], BEAK, 4, 2, 1)
    carve([[(-6 * grow, y), (6 * grow, y), (0, y + 10 * grow)]], BEAK, 6, 2.5, 2)

    # the feathers, cut in: down each wing, and along the tail
    feathers = [turn(line, (-17, -60), wing) for line in ([(-19, -52), (-22, -34), (-21, -18)], [(-24, -52), (-28, -34), (-25, -20)])]
    feathers += [mirror(line) for line in feathers]
    cuts = blur(mask(lines=feathers, width=1.3), 1) * alpha
    if rise > 6:                        # (only on the part of the tail that can be seen)
        lines = [[(0, -54), (0, -54 - 0.95 * rise)], [(-5, -53), (-5 - 0.7 * rise, -53 - 0.8 * rise)], [(5, -53), (5 + 0.7 * rise, -53 - 0.8 * rise)]]
        seen = tailMask * (1 - np.maximum.reduce([body, wings, neck, head]))
        cuts = np.maximum(cuts, blur(mask(lines=lines, width=1.3), 1) * seen)
    height -= 2.5 * k * cuts
    rgb *= (1 - 0.3 * cuts)[..., None]

    # the light, darker in the hollows where one part meets another, and the paint a little uneven
    diffuse, specular = heightLight(height, 18)
    hollows = np.clip(blur(height, 5 * k) - height, 0, None) / k
    rng = np.random.default_rng(59)
    texture = 1 + 0.08 * blur(rng.normal(0, 1, (h, w)).astype(np.float32), BS, 1)
    shade = (0.3 + 0.85 * diffuse) * np.clip(1 - 0.06 * hollows, 0.5, 1) * texture
    bird = toSurface(rgb * shade[..., None] + (45 * specular)[..., None], alpha * 255)

    # its glass eyes, each set in a pale ring
    for ex, ey in place([(-8.5 * grow, -77 + dip), (8.5 * grow, -77 + dip)]):
        pygame.draw.circle(bird, (226, 214, 186), (ex, ey), 3.8 * k)
        pygame.draw.circle(bird, (14, 10, 8), (ex, ey), 2.7 * k)
        pygame.draw.circle(bird, (250, 250, 245), (ex - 0.9 * k, ey - 0.9 * k), 0.9 * k)

    bird = pygame.transform.smoothscale(bird, (BIRD_W, BIRD_H))
    shadow, _ = makeShadow(bird, pygame.math.Vector2(0, 0))
    return bird, shadow


# The doors, closed: the left one and the right one, from the front and from behind
def drawDoors():
    w, h = 2 * DOOR_HALF, DOOR_HEIGHT
    xx, yy = screenGrid(w, h)
    dx = xx + 0.5 - DOOR_HALF
    sy = yy + DOOR_TOP
    d = doorDistance(dx, sy)
    rng = np.random.default_rng(53)
    planks = np.exp(-(((dx + 100) % 13) / 0.9) ** 2)

    doors = []
    for side in (-1, 1):
        dd = np.maximum(d, -side * dx)
        rgb = carved(dd, TRIM, 4, xx, yy, rng) * (1 - 0.35 * planks)[..., None]
        door = toSurface(rgb, np.clip(0.5 - dd, 0, 1) * 255)
        pygame.draw.circle(door, (110, 80, 36), (DOOR_HALF + side * 7, h * 0.58), 3)
        door = door.subsurface((0 if side < 0 else DOOR_HALF, 0, DOOR_HALF, h)).copy()
        back = pygame.transform.flip(door, True, False)
        back.fill((130, 130, 130), special_flags=pygame.BLEND_RGB_MULT)
        doors.append((door, back))
    return doors


def ramp(t, start, end):
    return min(1.0, max(0.0, (t - start) / (end - start)))


def ease(t, start, end):
    r = ramp(t, start, end)
    return r * r * (3 - 2 * r)


##==================================================================
## THE FACE
##==================================================================

class CuckooFace(AnalogueFace):

    name = "CUCKOO"
    centre = (CX, DIAL_Y)
    radius = DIAL_RADIUS
    statusColour = TEXT_COLOUR
    statusFonts = SERIF_FONTS
    statusItalic = True

    def build(self, chimeVolume, tickVolume):
        self.wall = drawWall()
        self.house, self.houseX = drawHouse()
        self.chain = drawChain()
        self.weight = drawWeight()
        self.dial = drawDial()
        self.hands = makeHands()
        self.nut = dome(round(8 * DIAL_INNER / 160), (196, 154, 80))
        self.glass = None
        self.pendulum, self.pivot = drawPendulum()
        self.shadow, self.shadowPivot = makeShadow(self.pendulum, self.pivot)
        self.swings = {}                # the pendulum, turned, at each angle it has been drawn at
        self.doors = drawDoors()
        self.birds = {pose: makeBird(*pose) for pose in POSES}     # the cuckoo, and its shadow, in each pose
        self.call, self.whirr, self.clack, self.ticks = makeSounds(chimeVolume, tickVolume)
        self.cues = {n: Cue(self, n) for n in range(1, 13)}
        self.show = None                # the cuckoo coming out to call: when, and what it does
        self.pose = None
        self.swing = 0
        self.weightKey = None
        self.tops = None
        self.background = self.wall

    def sounds(self):
        return [self.call, self.whirr, self.clack] + self.ticks

    def tickSounds(self):
        return self.ticks

    def chime(self, hour, minute):
        count = callsAt(hour, minute)
        if not count:
            return []
        shut = FIRST_CALL + (count - 1) * CALL_GAP + STAY + DOORS_SHUT
        return ([(0, self.cues[count]), (0, self.whirr), (DOOR_START, self.clack)] +
                [(FIRST_CALL + i * CALL_GAP, self.call) for i in range(count)] + [(shut, self.clack)])

    # Tick, tock, as the pendulum reaches each end of its swing
    beats = BEATS

    # (BEATS need not be a whole number: now is the second the beat falls in, and beat how far
    # into it, in beats, so together they count the beats since 1970)
    def beatSound(self, now, beat):
        return self.ticks[round(now.timestamp() * BEATS + beat) % 2]

    def angles(self, now):
        hours, minutes, _ = super().angles(now)
        return hours, minutes, 0

    # The cuckoo comes out to call count times (see Cue), or goes back in early
    def startShow(self, count):
        calls = [FIRST_CALL + i * CALL_GAP for i in range(count)]
        self.show = SimpleNamespace(start=time.time(), calls=calls, retreat=calls[-1] + STAY)

    def endShow(self):
        if self.show:
            self.show.retreat = min(self.show.retreat, time.time() - self.show.start)

    # How far the doors are open and the bird out, and how far it is bowing and its beak open
    def cuckooPose(self):
        show = self.show
        if show is None:
            return None
        t = time.time() - show.start
        back = show.retreat
        if t > back + DOORS_SHUT + 0.1:
            self.show = None
            return None

        doors = max(0.0, ease(t, DOOR_START, DOOR_START + DOOR_SWING) - ease(t, back + DOORS_SHUT - 0.22, back + DOORS_SHUT))
        out = ease(t, OUT_START, OUT_START + OUT_MOVE) * (1 - ease(t, back, back + GO_IN))
        call = beak = 0.0
        if t < back:
            for at in show.calls:
                call = max(call, ease(t, at - 0.12, at) * (1 - ease(t, at + 0.62, at + 0.9)))
                for start, end in ((at, at + CU_SECONDS), (at + CU_TO_KOO, at + CU_TO_KOO + KOO_SECONDS)):
                    beak = max(beak, ramp(t, start, start + 0.04) * (1 - ramp(t, end - 0.06, end)))
        return doors, out, call, beak

    # The wall with the weights and the chains on it, and the house over them
    def buildScene(self, tops):
        scene = self.wall.copy()
        chainTop = BASE_Y - 20
        for side, top in zip((-1, 1), tops):
            x = CX + side * WEIGHT_X
            length = top + 8 - chainTop
            chain = self.chain.subsurface((0, CHAIN_H - length, CHAIN_W, length))
            for image, where in ((chain, (x - CHAIN_W / 2, chainTop)), (self.weight, (x - self.weight.get_width() / 2, top))):
                shadow, _ = makeShadow(image, pygame.math.Vector2(0, 0))
                scene.blit(shadow, (where[0] + 4, where[1] + 8))
            scene.blit(chain, (x - CHAIN_W / 2, chainTop))
            scene.blit(self.weight, (x - self.weight.get_width() / 2, top))
        scene.blit(self.house, (self.houseX, 0))
        return scene

    def update(self, now):
        key = (now.date(), now.hour, now.minute)
        if key != self.weightKey:
            self.weightKey = key
            tops = weightTops(now)
            if tops != self.tops:
                self.tops = tops
                self.background = self.buildScene(tops)
                self.slowKey = None

        super().update(now)
        self.swing = SWING * math.cos(math.pi * BEATS * now.timestamp())
        self.pose = self.cuckooPose()

    def draw(self, surface):
        super().draw(surface)
        self.drawPendulum(surface)
        self.drawCuckoo(surface)

    def drawPendulum(self, surface):
        key = round(self.swing * 4)
        if key not in self.swings:
            angle = key / 4
            self.swings[key] = (Hand.turned(self.shadow, self.shadowPivot, angle, (CX + 12, PIVOT_Y + 16)),
                                Hand.turned(self.pendulum, self.pivot, angle, (CX, PIVOT_Y)))
        surface.set_clip(pygame.Rect(0, CLIP_Y, scr.SCREEN_WIDTH, scr.SCREEN_HEIGHT - CLIP_Y))
        for image, rect in self.swings[key]:
            surface.blit(image, rect)
        surface.set_clip(None)

    def drawCuckoo(self, surface):
        if self.pose is None:
            for (door, _), x in zip(self.doors, (CX - DOOR_HALF, CX)):
                surface.blit(door, (x, DOOR_TOP))
            return

        doors, out, call, beak = self.pose
        if out > 0.5:
            self.drawDoors(surface, doors)
            self.drawBird(surface, out, call, beak)
        else:
            self.drawBird(surface, out, call, beak)
            self.drawDoors(surface, doors)

    # Each door turns on its hinge, out past square to the wall
    def drawDoors(self, surface, opened):
        k = math.cos(math.radians(112 * opened))
        width = max(1, round(DOOR_HALF * abs(k)))
        shade = round(255 * ((0.6 + 0.4 * k) if k >= 0 else 0.5))
        for (door, back), side in zip(self.doors, (-1, 1)):
            image = pygame.transform.smoothscale(door if k >= 0 else back, (width, DOOR_HEIGHT))
            image.fill((shade, shade, shade), special_flags=pygame.BLEND_RGB_MULT)
            hinge = CX + side * DOOR_HALF
            x = hinge if (k >= 0) == (side < 0) else hinge - width
            surface.blit(image, (x, DOOR_TOP))

    # The bird comes forward out of the dark, growing and coming into the light
    def drawBird(self, surface, out, call, beak):
        if out <= 0.01:
            return
        image, shadow = self.birds[poseFor(call, beak)]

        scale = 0.6 + 0.4 * out
        feet = (CX, DOOR_BOTTOM + 1 - 10 * (1 - out))
        if out >= 1:                    # out on its perch, in front of the house, with its shadow on it
            surface.blit(shadow, (feet[0] - BIRD_FEET[0] - 10 + 5, feet[1] - BIRD_FEET[1] - 10 + 7))
        else:
            image = pygame.transform.smoothscale(image, (round(BIRD_W * scale), round(BIRD_H * scale)))
            light = round(255 * (0.3 + 0.7 * out))
            image.fill((light, light, light), special_flags=pygame.BLEND_RGB_MULT)
            doorway = pygame.Rect(CX - DOOR_HALF, DOOR_TOP, 2 * DOOR_HALF, DOOR_HEIGHT)
            surface.set_clip(doorway.inflate(round(out * out * 240), round(out * out * 240)))
        surface.blit(image, (round(feet[0] - BIRD_FEET[0] * scale), round(feet[1] - BIRD_FEET[1] * scale)))
        surface.set_clip(None)
