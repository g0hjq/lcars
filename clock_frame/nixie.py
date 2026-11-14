"""
nixie.py

A Nixie tube clock: six tall glass tubes on a walnut base, showing the hours, minutes and
seconds in glowing orange wire digits, with small neon dots between them that blink with
the seconds. Inside each tube the other nine digits can be seen, unlit, behind a fine hexagonal
mesh, and each digit fades into the next, as the neon does. Every ROLL_MINUTES the tubes run
through all their digits for a moment, as real Nixie clocks do to keep them from wearing
unevenly. The date is engraved on a brass plate on the base.

It makes no sound but the time pips before each hour: five short ones on the last five
seconds, and a long one on the hour.
"""

import math
import datetime
import pygame
import numpy as np
import screens as scr
import synth
from .common import (Face, SS, LIGHT, screenGrid, smoothstep, waves, toSurface, lighting, bevel,
                     roundedBox, vignette, sysFont, SERIF_FONTS, makeSound)

##==================================================================
## SETTINGS (they are in settings.py, next to lcars.py)
##==================================================================

from settings import (
    NIXIE_HOURS_24 as HOURS_24,
    NIXIE_ROLL_MINUTES as ROLL_MINUTES,
    NIXIE_ROLL_SECONDS as ROLL_SECONDS,
    NIXIE_FADE_SECONDS as FADE_SECONDS,
    NIXIE_PIPS as PIPS,
    NIXIE_PIP_LOUDNESS as PIP_LOUDNESS,
    NIXIE_TUBE_W as TUBE_W,
    NIXIE_TUBE_H as TUBE_H,
    NIXIE_PAIR_GAP as PAIR_GAP,
    NIXIE_COLON_GAP as COLON_GAP,
    NIXIE_BASE_TOP as BASE_TOP,
    NIXIE_BASE_BOTTOM as BASE_BOTTOM,
    NIXIE_SOCKET_H as SOCKET_H,
    NIXIE_DIGIT_HALF_W as DIGIT_HALF_W,
    NIXIE_DIGIT_HALF_H as DIGIT_HALF_H,
    NIXIE_NEON as NEON,
    NIXIE_NEON_CORE as NEON_CORE,
    NIXIE_WIRE as WIRE,
    NIXIE_WALNUT as WALNUT,
    NIXIE_PLATE as PLATE,
    NIXIE_TEXT_COLOUR as TEXT_COLOUR,
)
from settings import NIXIE_DIGIT_Y

DIGIT_Y = NIXIE_DIGIT_Y * TUBE_H    # the middle of the digits, from the top of the glass


##==================================================================
## THE DIGITS, as wire paths
##==================================================================

# Points round part of an ellipse, from angle a0 to a1 (degrees: 0 is to the right, 90 down)
def arc(cx, cy, rx, ry, a0, a1, n=60):
    angles = np.radians(np.linspace(a0, a1, n))
    return [(cx + rx * math.cos(a), cy + ry * math.sin(a)) for a in angles]


# The wire paths of each digit, in a box from -1 to 1 each way (y down)
def digitPaths():
    six = [arc(0, 0.42, 1, 0.58, 0, 360), arc(1.25, 0.42, 2.25, 1.42, 180, 252)]
    return {
        0: [arc(0, 0, 1, 1, 0, 360)],
        1: [[(-0.45, -0.72), (0, -1), (0, 1)]],
        2: [arc(0, -0.48, 0.95, 0.52, 195, 380) + [(-1, 1), (1, 1)]],
        3: [arc(0, -0.5, 0.85, 0.5, 200, 450) + arc(0, 0.48, 1, 0.52, 270, 520)],
        4: [[(0.45, 1), (0.45, -1), (-1, 0.4), (1, 0.4)]],
        5: [[(0.9, -1), (-0.75, -1), (-0.88, -0.05)] + arc(0, 0.42, 1, 0.58, 225, 515)],
        6: six,
        7: [[(-1, -1), (1, -1), (-0.25, 1)]],
        8: [arc(0, -0.53, 0.78, 0.47, 0, 360), arc(0, 0.47, 1, 0.53, 0, 360)],
        9: [[(-x, -y) for x, y in path] for path in six],
    }


# Draws the paths of a digit in white on black, as a numpy array of 0 to 1, w x h, with
# its middle at (cx, cy), scaled by scale, the wire `width` pixels thick
def strokeMask(paths, w, h, cx, cy, scale, width):
    big = pygame.Surface((w * SS, h * SS))
    big.fill((0, 0, 0))
    thick = max(1, round(width * SS))
    for path in paths:
        points = [((cx + x * DIGIT_HALF_W * scale) * SS, (cy + y * DIGIT_HALF_H * scale) * SS) for x, y in path]
        pygame.draw.lines(big, (255, 255, 255), False, points, thick)
        for p in points:
            pygame.draw.circle(big, (255, 255, 255), p, thick / 2)
    small = pygame.transform.smoothscale(big, (w, h))
    return pygame.surfarray.array3d(small)[..., 0].T.astype(np.float32) / 255


# A soft blur of a 0 to 1 array, by shrinking it and growing it back
def blur(mask, factor):
    h, w = mask.shape
    surface = toSurface(np.dstack([mask * 255] * 3))
    small = pygame.transform.smoothscale(surface, (max(1, w // factor), max(1, h // factor)))
    small = pygame.transform.smoothscale(small, (max(1, w // (factor * 2)), max(1, h // (factor * 2))))
    back = pygame.transform.smoothscale(small, (w, h))
    return pygame.surfarray.array3d(back)[..., 0].T.astype(np.float32) / 255


# A glowing lit digit, as a picture TUBE_W x TUBE_H to put over its tube
def litDigit(paths):
    core = strokeMask(paths, TUBE_W, TUBE_H, TUBE_W / 2, DIGIT_Y, 1.0, 3.6)
    halo = blur(strokeMask(paths, TUBE_W, TUBE_H, TUBE_W / 2, DIGIT_Y, 1.0, 16), 6)
    wide = blur(strokeMask(paths, TUBE_W, TUBE_H, TUBE_W / 2, DIGIT_Y, 1.0, 40), 16)
    glow = np.clip(1.1 * halo + 0.5 * wide, 0, 1)
    alpha = np.clip(core + glow * 0.85, 0, 1) * np.clip(0.5 - glassDistance()[0], 0, 1)
    rgb = (np.array(NEON_CORE, np.float32) * core[..., None] + np.array(NEON, np.float32) * (glow * (1 - core))[..., None])
    with np.errstate(invalid="ignore", divide="ignore"):
        rgb = np.where(alpha[..., None] > 0, rgb / np.maximum(alpha, 1e-3)[..., None], 0)
    return toSurface(rgb, alpha * 255)


# A small round neon dot, glowing, for between the pairs of tubes
def neonDot(radius):
    size = int(radius * 8)
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    r = np.hypot(xx - size / 2, yy - size / 2)
    core = np.clip(radius - r + 0.5, 0, 1)
    glow = np.exp(-(r / (radius * 1.8)) ** 2)
    alpha = np.clip(core + 0.8 * glow, 0, 1)
    rgb = np.array(NEON_CORE, np.float32) * core[..., None] + np.array(NEON, np.float32) * (1 - core)[..., None]
    return toSurface(rgb, alpha * 255)


##==================================================================
## THE TUBES AND THE BASE
##==================================================================

# How far each pixel of a tube's picture is from the edge of its glass (minus inside): a
# round top, straight sides, and a flat bottom going into the socket
def glassDistance():
    yy, xx = np.mgrid[0:TUBE_H, 0:TUBE_W].astype(np.float32) + 0.5
    half = TUBE_W / 2
    side = np.abs(xx - half) - half + 1
    top = np.hypot(xx - half, yy - half) - half + 1
    return np.where(yy < half, top, side), xx, yy


# The distance to the nearest line of a honeycomb whose cells are `size` across
def honeycomb(x, y, size):
    s = size / math.sqrt(3)
    q = (math.sqrt(3) / 3 * x - y / 3) / s
    r = (2 / 3 * y) / s
    cx, cz = q, r
    cy = -cx - cz
    rx, ry, rz = np.round(cx), np.round(cy), np.round(cz)
    dx, dy, dz = np.abs(rx - cx), np.abs(ry - cy), np.abs(rz - cz)
    fixX = (dx > dy) & (dx > dz)
    fixY = ~fixX & (dy > dz)
    rx = np.where(fixX, -ry - rz, rx)
    rz = np.where(~fixX & ~fixY, -rx - ry, rz)
    px = s * math.sqrt(3) * (rx + rz / 2)
    py = s * 1.5 * rz
    lx, ly = np.abs(x - px), np.abs(y - py)
    return s * math.sqrt(3) / 2 - np.maximum(lx, lx * 0.5 + ly * math.sqrt(3) / 2)


# The inside of a tube, behind the lit digit: dark, warmed by the glow, with the other
# digits' wires and the rods that hold them
def tubeBack(paths):
    d, xx, yy = glassDistance()
    inside = np.clip(0.5 - d, 0, 1)
    cx, cy = TUBE_W / 2, DIGIT_Y
    warm = np.exp(-(((xx - cx) / 95) ** 2 + ((yy - cy) / 175) ** 2))
    rgb = np.array([14, 11, 10], np.float32) + np.array([62, 20, 4], np.float32) * (0.55 * warm)[..., None]

    # the digits stand one behind another, the further ones a little smaller and darker
    order = [1, 6, 2, 7, 5, 0, 4, 9, 8, 3]
    for depth, digit in enumerate(reversed(order)):
        mask = strokeMask(paths[digit], TUBE_W, TUBE_H, cx, cy, 1.0 - 0.012 * (9 - depth), 1.8)
        shade = 0.55 + 0.45 * depth / 9
        rgb = rgb * (1 - mask[..., None]) + np.array(WIRE, np.float32) * shade * mask[..., None]

    # two thin rods down the sides holding the digits
    for rx in (cx - DIGIT_HALF_W - 14, cx + DIGIT_HALF_W + 14):
        rod = np.clip(1.6 - np.abs(xx - rx), 0, 1) * (yy > cy - DIGIT_HALF_H - 30)
        rgb = rgb * (1 - rod[..., None]) + np.array([70, 62, 56], np.float32) * rod[..., None]

    return toSurface(rgb, inside * 255)


# The front of a tube, over the lit digit: the mesh, the silvered top, and the light on the glass
def tubeFront():
    d, xx, yy = glassDistance()
    inside = np.clip(0.5 - d, 0, 1)
    half = TUBE_W / 2

    mesh = np.clip(1.1 - honeycomb(xx, yy, 15), 0, 1) * (yy > DIGIT_Y - DIGIT_HALF_H - 40) * (yy < TUBE_H - 22)
    mesh *= smoothstep(4, 18, -d)
    getter = smoothstep(half * 0.75, half * 0.2, yy) * 0.55
    streak = 0.55 * np.exp(-((xx - 0.2 * TUBE_W) / 5) ** 2) * smoothstep(half * 0.5, half, yy)
    streak += 0.25 * np.exp(-((xx - 0.84 * TUBE_W) / 3.5) ** 2) * smoothstep(half * 0.6, half * 1.1, yy)
    domeShine = 0.5 * np.exp(-((np.hypot(xx - half, yy - half) - half * 0.82) / 4) ** 2) * (xx < half) * (yy < half)
    rim = 0.4 * np.exp(-(d / 1.5) ** 2)

    light = np.clip(streak + domeShine + rim, 0, 1)
    alpha = np.clip(0.4 * mesh + getter + light, 0, 1)
    rgb = (np.array([34, 30, 28], np.float32) * (0.4 * mesh)[..., None]
           + np.array([92, 82, 72], np.float32) * getter[..., None]
           + np.array([255, 245, 235], np.float32) * light[..., None])
    with np.errstate(invalid="ignore", divide="ignore"):
        rgb = np.where(alpha[..., None] > 0, rgb / np.maximum(alpha, 1e-3)[..., None], 0)
    return toSurface(rgb, alpha * np.maximum(inside, np.clip(1 - np.abs(d), 0, 1)) * 255)


# The x of the left of each tube, and the x of each pair of dots
def layout():
    total = 6 * TUBE_W + 3 * PAIR_GAP + 2 * COLON_GAP
    x = (scr.SCREEN_WIDTH - total) / 2
    tubes, colons = [], []
    for pair in range(3):
        tubes.append(round(x))
        tubes.append(round(x + TUBE_W + PAIR_GAP))
        x += 2 * TUBE_W + PAIR_GAP
        if pair < 2:
            colons.append(round(x + COLON_GAP / 2))
            x += COLON_GAP
    return tubes, colons


# A dark room, a desk, the walnut base with the tubes' sockets on it, and the tubes' insides
def drawBackground(tubes, back):
    w, h = scr.SCREEN_WIDTH, scr.SCREEN_HEIGHT
    xx, yy = screenGrid(w, h)
    rng = np.random.default_rng(41)
    tubeTop = BASE_TOP - SOCKET_H - TUBE_H
    mid = (tubeTop + BASE_TOP) / 2

    # the wall, lit orange by the tubes
    rgb = np.array([16, 13, 12], np.float32) * (1 + 0.06 * waves(xx, yy, 5, 300, rng))[..., None]
    glow = np.exp(-(((xx - w / 2) / 900) ** 2 + ((yy - mid) / 420) ** 2))
    rgb += np.array([70, 26, 6], np.float32) * (0.55 * glow)[..., None]

    # the desk, dark wood, with the glow reflected in it
    desk = yy >= BASE_BOTTOM
    grain = 0.85 + 0.08 * np.sin(yy * 0.9 + 6 * waves(xx * 0.2, yy, 4, 200, rng)) + 0.05 * waves(xx * 0.3, yy * 4, 5, 100, rng)
    deskRgb = np.array([46, 30, 20], np.float32) * grain[..., None]
    deskRgb += np.array([90, 34, 8], np.float32) * (0.5 * np.exp(-(((xx - w / 2) / 800) ** 2 + ((yy - BASE_BOTTOM) / 70) ** 2)))[..., None]
    deskRgb *= (1 - 0.6 * np.exp(-((yy - BASE_BOTTOM) / 14) ** 2) * (np.abs(xx - w / 2) < 850))[..., None]
    rgb = np.where(desk[..., None], deskRgb, rgb)

    # the base: walnut, rounded at its edges
    left, right = tubes[0] - 60, tubes[-1] + TUBE_W + 60
    d = roundedBox(xx, yy, (left + right) / 2, (BASE_TOP + BASE_BOTTOM) / 2, (right - left) / 2, (BASE_BOTTOM - BASE_TOP) / 2, 14)
    inside = np.clip(0.5 - d, 0, 1)
    nx, ny, nz = bevel(-d, 10)
    diffuse, specular = lighting(nx, ny, nz, 30)
    wander = yy * 1.0 + 9 * waves(xx * 0.15, yy, 5, 80, rng)
    wood = 0.75 + 0.12 * np.sin(wander * 0.55) + 0.08 * waves(xx * 0.1, wander, 5, 30, rng)
    baseRgb = np.array(WALNUT, np.float32) * (wood * (0.45 + 0.75 * diffuse))[..., None] + (120 * specular)[..., None]
    baseRgb += np.array([80, 30, 6], np.float32) * (0.5 * smoothstep(BASE_TOP + 40, BASE_TOP, yy))[..., None]
    rgb = rgb * (1 - inside[..., None]) + baseRgb * inside[..., None]

    # the sockets: short black cylinders
    half = TUBE_W / 2 - 4
    across = np.linspace(-1, 1, int(2 * half))
    nz = np.sqrt(np.clip(1 - across ** 2, 0, 1))
    lit = np.clip(across * LIGHT[0] + nz * LIGHT[2], 0, 1)
    socket = np.array([26, 24, 24], np.float32) * (0.5 + 0.9 * lit)[:, None] + (70 * lit ** 20)[:, None]
    for x in tubes:
        left = round(x + 4)
        rgb[BASE_TOP - SOCKET_H:BASE_TOP, left:left + len(across)] = socket[None, :, :]

    picture = toSurface(vignette(rgb, xx, yy, 0.5))
    for x in tubes:
        picture.blit(back, (x, tubeTop))
    return picture


# The brass plate on the base, with the date engraved on it
def drawPlate(now):
    w, h = 470, 64
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    d = roundedBox(xx, yy, w / 2, h / 2, w / 2 - 1, h / 2 - 1, 6)
    nx, ny, nz = bevel(-d, 5)
    diffuse, specular = lighting(nx, ny, nz, 40)
    brushed = 1 + 0.04 * np.sin(yy * 2.7 + np.sin(xx * 0.05) * 2)
    rgb = np.array(PLATE, np.float32) * (brushed * (0.4 + 0.75 * diffuse))[..., None] + (180 * specular)[..., None]
    plate = toSurface(rgb, np.clip(0.5 - d, 0, 1) * 255)

    font = sysFont(SERIF_FONTS, 30)
    text = now.strftime("%A %d %B %Y").upper().replace(" 0", " ")
    for offset, colour in (((1, 1), (236, 210, 150)), ((0, 0), (52, 38, 18))):
        image = font.render(text, True, colour)
        plate.blit(image, image.get_rect(center=(w / 2 + offset[0], h / 2 + offset[1])))
    return plate


##==================================================================
## THE SOUND
##==================================================================

# Five short pips and a long one, the long one starting five seconds after the first
def makePips(volume):
    t = synth.times(5.6)
    sound = np.zeros_like(t)
    for start, length in ((0, 0.1), (1, 0.1), (2, 0.1), (3, 0.1), (4, 0.1), (5, 0.5)):
        on = (t >= start) & (t < start + length)
        ramp = np.minimum(1.0, np.minimum(t - start, start + length - t) / 0.004)
        sound += np.where(on, np.sin(2 * math.pi * 1000 * t) * ramp, 0)
    return synth.makeSound(sound, volume)


##==================================================================
## THE FACE
##==================================================================

class NixieFace(Face):

    name = "NIXIE"
    statusColour = TEXT_COLOUR

    def build(self, chimeVolume, tickVolume):
        paths = digitPaths()
        self.tubes, self.colons = layout()
        self.background = drawBackground(self.tubes, tubeBack(paths))
        self.front = tubeFront()
        self.lit = {digit: litDigit(path) for digit, path in paths.items()}
        self.dot = neonDot(7)
        self.pips = makePips(chimeVolume * PIP_LOUDNESS) if PIPS else None
        self.tubeTop = BASE_TOP - SOCKET_H - TUBE_H
        self.date = None
        self.plate = None
        self.enter()

    def sounds(self):
        return [self.pips]

    def enter(self):
        self.shown = [None] * 6         # the digit in each tube, the one before, and when it changed
        self.before = [None] * 6
        self.changed = [0.0] * 6

    # The pips start five seconds before the hour, so that the long one is on it
    def soundsAt(self, now):
        if self.pips and now.minute == 59 and now.second == 55:
            return [(0, self.pips, "chime")]
        return []

    def chime(self, hour, minute):
        return [(0, self.pips)] if minute == 0 and self.pips else []

    # The digit in each tube: None for one that is not lit
    @staticmethod
    def digits(now):
        hour = now.hour if HOURS_24 else (now.hour % 12 or 12)
        digits = [hour // 10, hour % 10, now.minute // 10, now.minute % 10, now.second // 10, now.second % 10]
        if not HOURS_24 and digits[0] == 0:
            digits[0] = None
        return digits

    # While the tubes are running through their digits: what each shows, or None when it has stopped
    @staticmethod
    def rolling(now, digits):
        if not ROLL_MINUTES or now.minute % ROLL_MINUTES or now.second >= ROLL_SECONDS + 1:
            return [None] * 6
        elapsed = now.second + now.microsecond / 1e6
        result = []
        for i, digit in enumerate(digits):
            if elapsed < ROLL_SECONDS * (0.45 + 0.11 * i):
                result.append(((digit or 0) + 1 + int(elapsed * 17 + i * 3)) % 10)
            else:
                result.append(None)
        return result

    def update(self, now):
        if now.date() != self.date:
            self.date = now.date()
            self.plate = drawPlate(now)

        clock = now.timestamp()
        digits = self.digits(now)
        rolls = self.rolling(now, digits)
        for i, digit in enumerate(digits):
            want = rolls[i] if rolls[i] is not None else digit
            if want != self.shown[i]:
                rolling = rolls[i] is not None or self.shown[i] is None
                self.before[i] = None if rolling else self.shown[i]
                self.shown[i] = want
                self.changed[i] = clock - (FADE_SECONDS if rolling else 0)
        self.clock = clock
        self.blink = now.microsecond < 500000

    def draw(self, surface):
        surface.blit(self.background, (0, 0))
        for i, x in enumerate(self.tubes):
            fade = min(1.0, (self.clock - self.changed[i]) / FADE_SECONDS)
            for digit, alpha in ((self.before[i], 1 - fade), (self.shown[i], fade)):
                if digit is not None and alpha > 0.01:
                    image = self.lit[digit]
                    image.set_alpha(round(255 * alpha))
                    surface.blit(image, (x, self.tubeTop))
            surface.blit(self.front, (x, self.tubeTop))

        if self.blink:
            mid = self.tubeTop + DIGIT_Y
            for x in self.colons:
                for y in (mid - 62, mid + 62):
                    surface.blit(self.dot, self.dot.get_rect(center=(x, round(y))))

        if self.plate:
            surface.blit(self.plate, self.plate.get_rect(center=(scr.SCREEN_WIDTH // 2, (BASE_TOP + BASE_BOTTOM) // 2)))
