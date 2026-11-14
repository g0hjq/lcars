"""
aquarium.py

A tropical fish tank: fish of several kinds swimming about at different depths, a school
of tiny neon fish, plants swaying in the current, bubbles rising from an air stone, and
sunlight rippling on the sand.

The OK button (or Enter) sprinkles food on the water. It sinks slowly, and the fish dart
up to eat it.

At night (the clock's quiet hours, see CLOCK_QUIET_FROM in settings.py) the tank light
goes down, the fish rest near the bottom, and the bubbling is silent.

Everything is drawn by the program: the fish when it starts (each in a few positions of
its tail), the plants, bubbles and ripples as it goes.
"""

import datetime
import math
import random
import numpy as np
import pygame
import screens as scr
import synth
from clock_frame.clock import ClockScreen

##==================================================================
## SETTINGS (they are in settings.py, next to lcars.py)
##==================================================================

# Its settings are in settings.py (next to lcars.py)
from settings import (
    AQUARIUM_SOUND as SOUND,
    AQUARIUM_SOUND_VOLUME as SOUND_VOLUME,
    AQUARIUM_SAND_TOP as SAND_TOP,
    AQUARIUM_SURFACE as SURFACE,
    AQUARIUM_TAIL_FRAMES as TAIL_FRAMES,
    AQUARIUM_FOOD_FLAKES as FOOD_FLAKES,
    AQUARIUM_STOCK as STOCK,
    AQUARIUM_KINDS as KINDS,
    AQUARIUM_WATER_TOP as WATER_TOP,
    AQUARIUM_WATER_BOTTOM as WATER_BOTTOM,
    AQUARIUM_NIGHT as NIGHT,
)

W, H = scr.SCREEN_WIDTH, scr.SCREEN_HEIGHT


##==================================================================
## THE SOUNDS
##==================================================================

# A little bubble: a quick rising tone that dies away
def bloop(rng):
    seconds = 0.08
    t = synth.times(seconds)
    f0 = rng.uniform(380, 1100)
    pitch = f0 * (1 + 1.2 * t / seconds)
    phase = 2 * np.pi * np.cumsum(pitch) / synth.SAMPLE_RATE
    return np.sin(phase) * np.exp(-t / 0.02)


# Several seconds of bubbling and the hum of the pump, to play round and round
def makeBubbling():
    rng = np.random.default_rng(8)
    seconds = 8.0
    left = np.zeros(int(seconds * synth.SAMPLE_RATE))
    right = np.zeros_like(left)
    for _ in range(int(seconds * 9)):
        sound = bloop(rng) * rng.uniform(0.15, 0.6)
        at = rng.uniform(0, seconds - 0.1)
        pan = rng.uniform(0.55, 0.9)            # the air stone is to the right
        synth.mixIn(left, sound * (1 - pan), at)
        synth.mixIn(right, sound * pan, at)
    hum = synth.smooth(synth.noise(seconds, rng), 60) * 0.6
    left += hum
    right += hum
    return synth.makeSound(np.column_stack((left, right)), SOUND_VOLUME)


# Food landing on the water
def makePlip():
    t = synth.times(0.12)
    pitch = 700 + 2400 * t / 0.12
    phase = 2 * np.pi * np.cumsum(pitch) / synth.SAMPLE_RATE
    return synth.makeSound(np.sin(phase) * np.exp(-t / 0.03), SOUND_VOLUME * 1.4)


##==================================================================
## DRAWING THE FISH (once, at the start)
##==================================================================

def shade(colour, factor):
    return tuple(int(max(0, min(255, c * factor))) for c in colour)


def mix(a, b, f):
    return tuple(int(x + (y - x) * f) for x, y in zip(a, b))


def smoothstep(edge0, edge1, x):
    t = np.clip((x - edge0) / (edge1 - edge0), 0, 1)
    return t * t * (3 - 2 * t)


# Rounds off the corners of a line of points (Chaikin's way: each corner is cut off, twice),
# keeping its two ends where they are
def rounded(points, times=2):
    for _ in range(times):
        new = [points[0]]
        for (x0, y0), (x1, y1) in zip(points, points[1:]):
            new.append((0.75 * x0 + 0.25 * x1, 0.75 * y0 + 0.25 * y1))
            new.append((0.25 * x0 + 0.75 * x1, 0.25 * y0 + 0.75 * y1))
        new.append(points[-1])
        points = new
    return points


# A fin: a see-through skin over bony rays that fan out from its root, darker at its curved
# edge. root is where it joins the body, and outline the points round its edge.
def drawFin(surface, root, outline, colour, edge, alpha, ss):
    smooth = rounded(outline)
    pygame.draw.polygon(surface, (*colour, alpha), smooth)
    for point in rounded(outline, 1)[2:-2]:
        pygame.draw.line(surface, (*shade(colour, 0.65), min(255, alpha + 40)), root, point, max(1, ss // 2))
    pygame.draw.lines(surface, (*(edge or shade(colour, 0.7)), min(255, alpha + 60)), False, smooth[2:-2], max(1, ss))


# Pictures of a fish facing right, its tail and the back of its body in TAIL_FRAMES places,
# as it swims. The body is shaded as though round and lit from above, with scales, a darker
# back and a paler belly; far fish are hazier.
def drawFish(kind, length, haze):
    spec = KINDS[kind]
    ss = 2
    L = length * ss
    body = L * 0.76                     # the body, without the tail
    tall = spec["tall"] * body
    fins = 1.0 if spec.get("bigFins") else 0.3
    margin = L * 0.08                   # room for the tail to swing
    w = int(L * 1.1 + margin)
    h = int(tall * (1 + 2 * fins) + 12 * ss)
    tailX = L * 0.27 + margin           # where the tail meets the body
    midY = h / 2

    # half the body's height along it: slim where the tail joins, swelling smoothly to its
    # deepest a little behind the middle, then rounding off to the nose
    xs = np.linspace(0, 1, 80)
    rear = 0.5 - 0.5 * np.cos(np.pi * np.clip(xs / 0.48, 0, 1))
    front = np.sqrt(np.clip(1 - np.clip((xs - 0.48) / 0.52, 0, 1) ** 2.4, 0, 1))
    profile = 0.5 * tall * np.where(xs < 0.48, 0.24 + 0.76 * rear, front)
    if spec.get("snout"):
        profile *= 1 - 0.35 * np.clip((xs - 0.85) / 0.15, 0, 1)

    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    along = (xx - tailX) / body         # 0 at the tail, 1 at the nose
    half = np.interp(along, xs, profile)

    # the scales: a fine diamond pattern, smaller towards the head
    size = body * 0.018
    scales = np.sin((xx + yy * 1.2) / size) * np.sin((xx - yy * 1.2) / size)

    colour = np.array(spec["colour"], dtype=np.float32)
    belly = np.array(spec["belly"], dtype=np.float32)
    finColour = spec["fin"]
    tailColour = spec.get("tailColour", spec["fin"])
    frames = []

    for frame in range(TAIL_FRAMES):
        swing = math.sin(2 * math.pi * frame / TAIL_FRAMES)

        # the back half of the body bends with the tail
        def bend(a):
            return swing * tall * 0.16 * np.clip(0.6 - a, 0, None) ** 2 / 0.36

        def top(a):
            return midY + bend(a) - np.interp(a, xs, profile) * 1.05

        def bottom(a):
            return midY + bend(a) + np.interp(a, xs, profile) * 0.95

        def at(a, y):
            return (tailX + a * body, y)

        surface = pygame.Surface((w, h), pygame.SRCALPHA)
        surface.fill((*spec["colour"], 0))

        # the tail, swinging from where it meets the body
        root = (tailX + 3 * ss, midY + float(bend(0)))
        angle = swing * 0.38

        def turned(dx, dy):
            return (root[0] + dx * math.cos(angle) - dy * math.sin(angle),
                    root[1] + dx * math.sin(angle) + dy * math.cos(angle))

        span = tall * (0.6 if spec["tail"] != "long" else 1.0)
        reach = L * 0.27 * (0.95 if spec["tail"] != "long" else 1.2)
        if spec["tail"] == "fork":
            shape = [(0, 0)] + [(-1, -0.55), (-0.82, -0.36), (-0.68, -0.15), (-0.62, 0), (-0.68, 0.15), (-0.82, 0.36), (-1, 0.55)] + [(0, 0)]
        elif spec["tail"] == "round":
            shape = [(0, 0)] + [(-0.85 * math.cos(a), 0.5 * math.sin(a)) for a in np.linspace(-1.2, 1.2, 9)] + [(0, 0)]
        else:
            shape = [(0, 0)] + [(-0.75, -0.62), (-1.0, -0.5), (-0.85, -0.2), (-1.05, 0.05), (-0.95, 0.35), (-0.72, 0.64)] + [(0, 0)]
        tailPoints = [turned(dx * reach, dy * span) for dx, dy in shape]
        tailPoints[0] = turned(0, -0.1 * span)
        tailPoints[-1] = turned(0, 0.1 * span)
        drawFin(surface, root, tailPoints, tailColour, spec["edge"], 140 if spec["tail"] == "long" else 190, ss)

        # the fins on the back and the belly
        if spec.get("bigFins"):
            back = [at(0.65, top(0.65)), at(0.45, midY - tall * 0.95), at(0.25, midY - tall * 1.4),
                    at(0.17, midY - tall * 1.0), at(0.12, top(0.12))]
            under = [at(0.6, bottom(0.6)), at(0.4, midY + tall * 0.95), at(0.22, midY + tall * 1.4),
                     at(0.15, midY + tall * 1.0), at(0.1, bottom(0.1))]
        else:
            back = [at(0.72, top(0.72)), at(0.5, top(0.5) - tall * 0.34), at(0.32, top(0.32) - tall * 0.24),
                    at(0.2, top(0.2) - tall * 0.1), at(0.16, top(0.16))]
            under = [at(0.42, bottom(0.42)), at(0.32, bottom(0.32) + tall * 0.22), at(0.18, bottom(0.18) + tall * 0.12),
                     at(0.13, bottom(0.13))]
        drawFin(surface, at(0.45, midY), back, finColour, spec["edge"], 170, ss)
        drawFin(surface, at(0.3, midY), under, finColour, spec["edge"], 170, ss)

        # the body: its outline, then each pixel of it shaded
        outline = [at(a, top(a)) for a in xs] + [at(a, bottom(a)) for a in xs[::-1]]
        mask = pygame.Surface((w, h), pygame.SRCALPHA)
        mask.fill((0, 0, 0, 0))
        pygame.draw.polygon(mask, (255, 255, 255, 255), outline)
        inside = pygame.surfarray.array_alpha(mask).T.astype(np.float32) / 255

        centre = midY + bend(along)
        across = (yy - centre) / np.maximum(half, 1)        # -1 on the back, 1 on the belly
        round_ = np.sqrt(np.clip(1 - across ** 2, 0, 1))

        paint = colour + (belly - colour) * smoothstep(-0.1, 0.85, across)[..., None]
        for a0, a1, c in spec.get("bands", []):
            band = smoothstep(a0 - 0.012, a0 + 0.012, along) * (1 - smoothstep(a1 - 0.012, a1 + 0.012, along))
            if kind == "clown":
                rim = smoothstep(a0 - 0.04, a0 - 0.015, along) * (1 - smoothstep(a1 + 0.015, a1 + 0.04, along)) - band
                paint = paint * (1 - rim[..., None]) + np.array(spec["edge"], dtype=np.float32) * rim[..., None]
            paint = paint * (1 - band[..., None]) + np.array(c, dtype=np.float32) * band[..., None]
        for a0, a1, y0, y1, c in spec.get("stripes", []):
            stripe = (smoothstep(a0 - 0.03, a0 + 0.03, along) * (1 - smoothstep(a1 - 0.03, a1 + 0.03, along))
                      * smoothstep(y0 - 0.08, y0 + 0.08, across) * (1 - smoothstep(y1 - 0.08, y1 + 0.08, across)))
            paint = paint * (1 - stripe[..., None]) + np.array(c, dtype=np.float32) * stripe[..., None]

        light = 0.42 + 0.62 * np.clip(-across * 0.55 + round_ * 0.8, 0, 1)
        light *= 1 + 0.035 * scales * round_
        light *= 1 - 0.35 * (1 - round_) ** 3                # darker at the very edge, where it curves away
        shine = np.exp(-((across + 0.42) / 0.16) ** 2) * smoothstep(0.15, 0.5, along) * 70
        rgb = paint * light[..., None] + shine[..., None]

        # the lateral line along its side, a faint row of dots
        line = np.exp(-((across + 0.1 - 0.12 * (along - 0.5)) / 0.035) ** 2) * smoothstep(0.12, 0.2, along) \
            * (1 - smoothstep(0.7, 0.76, along)) * round_ * (0.5 + 0.5 * np.sin(xx / (1.6 * ss)))
        rgb *= (1 + 0.22 * line)[..., None]

        # the gill cover, a little darker behind its edge
        gill = np.exp(-((along - 0.74 - 0.04 * across ** 2) / 0.012) ** 2) * round_
        rgb *= (1 - 0.25 * gill)[..., None]

        far = np.array(WATER_BOTTOM, dtype=np.float32) * 1.4
        rgb = rgb * (1 - haze) + far * haze
        rgba = np.dstack((np.clip(rgb, 0, 255), inside * 255)).astype(np.uint8)
        bodyImage = pygame.image.frombuffer(rgba.tobytes(), (w, h), "RGBA")
        surface.blit(bodyImage, (0, 0))

        # the side fin, which flutters, in front of the body
        flutter = math.sin(4 * math.pi * frame / TAIL_FRAMES) * 0.2
        side = [at(0.68, midY + tall * 0.12), at(0.56, midY + tall * (0.12 + flutter * 0.5)),
                at(0.5, midY + tall * (0.34 + flutter)), at(0.6, midY + tall * 0.3), at(0.68, midY + tall * 0.12)]
        drawFin(surface, side[0], side, finColour, None, 110, ss)

        # the eye: a dark rim, a coloured ring, the pupil, and a glint of light
        eye = at(0.875, midY - tall * 0.1)
        radius = max(2.5 * ss, body * 0.05)
        pygame.draw.circle(surface, (20, 20, 22), eye, radius * 1.12)
        pygame.draw.circle(surface, spec["eye"], eye, radius)
        pygame.draw.circle(surface, (6, 6, 8), eye, radius * 0.6)
        pygame.draw.circle(surface, (255, 255, 255), (eye[0] - radius * 0.3, eye[1] - radius * 0.32), radius * 0.22)

        # the mouth
        nose = at(0.995, midY + tall * 0.05)
        pygame.draw.line(surface, shade(spec["colour"], 0.45), nose, at(0.95, midY + tall * 0.07), max(1, ss))

        frames.append(pygame.transform.smoothscale(surface, (w // ss, h // ss)))

    return frames


##==================================================================
## THE TANK (drawn once)
##==================================================================

def waves(xx, yy, count, scale, rng):
    total = np.zeros_like(xx)
    for _ in range(count):
        a = rng.uniform(0, math.pi)
        k = rng.uniform(0.6, 1.4) / scale
        total += np.sin((xx * math.cos(a) + yy * math.sin(a)) * k + rng.uniform(0, 6.3))
    return total / math.sqrt(count)


# A rock sitting half buried in the sand, with a shadow round its foot: rounded, bumpy, lit
# from above, speckled, and with a little green weed on top. Drawn into the picture rgb.
def addRock(rgb, cx, cy, rx, ry, rng, pebble=False):
    x0, x1 = int(max(0, cx - rx * 1.4)), int(min(W, cx + rx * 1.4))
    y0, y1 = int(max(0, cy - ry * 1.2)), int(min(H, cy + ry * 0.7))
    if x1 <= x0 or y1 <= y0:
        return
    yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
    dx, dy = (xx - cx) / rx, (yy - cy) / ry

    # the shadow on the sand round its foot
    shadow = np.exp(-(dx / 1.15) ** 2 - ((dy - 0.15) / 0.32) ** 2)
    rgb[y0:y1, x0:x1] *= (1 - 0.45 * shadow)[..., None]

    # its shape: a dome, flattened where it sinks into the sand, and bumpy
    squash = np.where(dy > 0, dy * 2.6, dy)
    bumps = 0.0 if pebble else waves(xx, yy, 6, rx * 0.35, rng) * 0.1 + waves(xx, yy, 6, rx * 0.1, rng) * 0.04
    dome = np.sqrt(np.clip(1 - dx * dx - squash * squash, 0, None))
    height = dome * ry * (1 + bumps)
    cover = np.clip(dome * min(rx, ry) * 0.6, 0, 1)

    gy, gx = np.gradient(height)
    nx, ny, nz = -gx, -gy, np.ones_like(gx)
    length = np.sqrt(nx * nx + ny * ny + nz * nz)
    light = np.array([-0.35, -0.8, 0.5])
    light = light / np.linalg.norm(light)
    diffuse = np.clip((nx * light[0] + ny * light[1] + nz * light[2]) / length, 0, 1)

    base = np.array(rng.choice([(110, 106, 100), (96, 92, 90), (122, 112, 98), (88, 90, 96), (130, 124, 112)]),
                    dtype=np.float32)
    speckle = 1 + rng.normal(0, 0.07, height.shape)
    colour = base * ((0.3 + 0.95 * diffuse) * speckle)[..., None]
    if not pebble:
        weed = np.clip(-ny / length - 0.55, 0, 1) * np.clip(waves(xx, yy, 5, rx * 0.2, rng) + 0.3, 0, 1)
        colour = colour * (1 - 0.6 * weed[..., None]) + np.array([60, 110, 50]) * diffuse[..., None] * 0.6 * weed[..., None]
    region = rgb[y0:y1, x0:x1]
    rgb[y0:y1, x0:x1] = region * (1 - cover[..., None]) + colour * cover[..., None]


def drawTank():
    rng = np.random.default_rng(21)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)

    depth = (yy / H)[..., None]
    water = np.array(WATER_TOP, dtype=np.float32) * (1 - depth) + np.array(WATER_BOTTOM, dtype=np.float32) * depth
    water *= (1 + 0.05 * waves(xx, yy, 5, 300, rng))[..., None]

    # the sand: grainy, with gentle ripples, a wavy top edge, and darker further back
    edge = SAND_TOP + 18 * np.sin(xx / 170) + 10 * np.sin(xx / 61 + 1)
    sandDepth = np.clip((yy - edge) / (H - SAND_TOP), 0, 1)
    sand = np.array([194, 172, 128], dtype=np.float32) * (0.6 + 0.45 * sandDepth)[..., None]
    sand *= (1 + 0.08 * np.sin(xx / 23 + 3 * np.sin(yy / 30)) + rng.normal(0, 0.08, (H, W)))[..., None]
    inSand = np.clip(yy - edge + 1, 0, 1)[..., None]
    rgb = water * (1 - inSand) + sand * inSand

    # the surface: a brighter band at the top
    rgb += (np.clip(1 - yy / SURFACE, 0, 1) ** 2 * 70)[..., None]

    # darker in the corners, as seen through the glass
    corner = ((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2
    rgb *= (1 - 0.35 * np.clip(corner - 0.4, 0, 1))[..., None]
    # rocks, and pebbles strewn over the sand, the furthest first
    for cx, cy, rx, ry in ((980, 952, 74, 44), (430, 935, 104, 64), (1540, 940, 94, 58), (1380, 910, 150, 96),
                           (260, 905, 176, 114)):
        addRock(rgb, cx, cy, rx, ry, rng)
    for _ in range(140):
        size = rng.uniform(4, 13)
        addRock(rgb, rng.uniform(20, W - 20), rng.uniform(905, H - 5), size, size * rng.uniform(0.55, 0.8), rng, pebble=True)

    surface = pygame.surfarray.make_surface(np.clip(rgb, 0, 255).astype(np.uint8).transpose(1, 0, 2))

    # the air stone, to the right
    pygame.draw.ellipse(surface, (60, 60, 66), (1640, 930, 70, 26))
    return surface


# A soft beam of sunlight slanting down through the water, as light to add to the picture,
# at a few strengths so that it can shimmer
def drawRay(width, rng):
    h = SAND_TOP
    yy, xx = np.mgrid[0:h, 0:width * 2].astype(np.float32)
    lean = rng.uniform(-0.25, 0.25)
    centre = width + lean * yy
    spread = width * (0.3 + 0.7 * yy / h)
    across = np.abs(xx - centre) / spread
    light = np.clip(1 - across, 0, 1) ** 2 * (1 - yy / h) * 36
    strengths = []
    for strength in np.linspace(0.35, 1.0, 6):
        rgb = light[..., None] * np.array([0.8, 0.95, 1.0]) * strength
        strengths.append(pygame.surfarray.make_surface(rgb.astype(np.uint8).transpose(1, 0, 2)))
    return strengths


##==================================================================
## PLANTS, BUBBLES AND FOOD
##==================================================================

class Plant:
    """A clump of leaves that sway in the current: long ribbons, or broader pointed blades.
    Each leaf is shaded in strips down its two halves, darker at its foot and paler and more
    see-through towards its tip, and twisting, so one half and then the other catches the light."""

    SEGMENTS = 9

    def __init__(self, x, y, height, colour, far):
        self.x, self.y = x, y
        colour = shade(mix(colour, WATER_BOTTOM, 0.45), 0.85) if far else colour
        broad = random.random() < 0.4
        self.leaves = []
        for _ in range(random.randint(3, 6)):
            leaf = dict(lean=random.uniform(-0.4, 0.4), height=height * random.uniform(0.55, 1.1),
                        width=random.uniform(8, 15) * (1.8 if broad else 1) * (0.7 if far else 1),
                        broad=broad, phase=random.uniform(0, 6.3), sway=random.uniform(0.12, 0.25))
            twist, turn = random.uniform(2, 5), random.uniform(0, 6.3)
            leaf["colours"] = []
            for i in range(self.SEGMENTS):
                f = (i + 0.5) / self.SEGMENTS
                tw = math.sin(f * twist + turn)
                along = 0.62 + 0.55 * f
                left = mix(shade(colour, along * (0.84 + 0.16 * tw)), (190, 230, 160), 0.12 * f)
                right = mix(shade(colour, along * (0.84 - 0.16 * tw)), (190, 230, 160), 0.12 * f)
                leaf["colours"].append((left, right))
            leaf["vein"] = shade(colour, 1.25)
            self.leaves.append(leaf)

    def draw(self, surface, t):
        n = self.SEGMENTS
        for leaf in self.leaves:
            step = leaf["height"] / n
            x, y = self.x, self.y
            angle = leaf["lean"]
            left, right, middle = [], [], []
            for i in range(n + 1):
                f = i / n
                if leaf["broad"]:
                    width = leaf["width"] * math.sin(math.pi * min(1.0, 0.1 + f * 0.95)) ** 0.8
                else:
                    width = leaf["width"] * (1 - f ** 2.5) + 0.5
                nx, ny = math.cos(angle), math.sin(angle)
                left.append((x - nx * width, y - ny * width))
                right.append((x + nx * width, y + ny * width))
                middle.append((x, y))
                angle = leaf["lean"] * (1 - f) + leaf["sway"] * f * math.sin(t * 0.7 + leaf["phase"] - f * 2.2)
                x += math.sin(angle) * step
                y -= math.cos(angle) * step
            for i, (leftColour, rightColour) in enumerate(leaf["colours"]):
                pygame.draw.polygon(surface, leftColour, (left[i], middle[i], middle[i + 1], left[i + 1]))
                pygame.draw.polygon(surface, rightColour, (middle[i], right[i], right[i + 1], middle[i + 1]))
            pygame.draw.lines(surface, leaf["vein"], False, middle[:-1], 1)


class Bubble:

    def __init__(self, x, y):
        self.x, self.y = x, y
        self.r = random.uniform(2.5, 8)
        self.speed = random.uniform(110, 180)
        self.phase = random.uniform(0, 6.3)

    def update(self, dt):
        self.y -= self.speed * dt
        self.phase += dt * 9
        self.r *= 1 + dt * 0.08
        return self.y > SURFACE

    def draw(self, surface):
        x = self.x + math.sin(self.phase) * 3
        pygame.draw.circle(surface, (210, 245, 255), (x, self.y), self.r, 1 if self.r < 5 else 2)
        pygame.draw.circle(surface, (255, 255, 255), (x - self.r * 0.35, self.y - self.r * 0.35), max(1, self.r * 0.25))


class Flake:

    def __init__(self, x):
        self.x, self.y = x, SURFACE - 10
        self.phase = random.uniform(0, 6.3)
        self.colour = random.choice([(214, 120, 60), (200, 170, 70), (170, 70, 50)])
        self.landed = None

    def update(self, dt, t):
        if self.y < SAND_TOP + 10:
            self.y += dt * 30
            self.phase += dt * 2
        elif self.landed is None:
            self.landed = t
        return self.landed is None or t - self.landed < 20

    def draw(self, surface):
        x = self.x + math.sin(self.phase) * 12
        pygame.draw.ellipse(surface, self.colour, (x - 4, self.y - 2, 8, 4))

    @property
    def position(self):
        return self.x + math.sin(self.phase) * 12, self.y


##==================================================================
## A FISH
##==================================================================

class Fish:

    def __init__(self, kind, length, depth, frames, school=None):
        self.kind = kind
        self.length = length * (1 - 0.4 * depth)
        self.depth = depth                  # 0 at the front of the tank, 1 at the back
        self.right = frames
        self.left = [pygame.transform.flip(f, True, False) for f in frames]
        self.school = school
        self.offset = (random.uniform(-90, 90), random.uniform(-45, 45))
        self.x, self.y = random.uniform(150, W - 150), random.uniform(150, SAND_TOP - 120)
        self.vx, self.vy = 0.0, 0.0
        self.target = self.newTarget()
        self.cruise = KINDS[kind]["speed"] * random.uniform(0.8, 1.2)
        self.facing = random.choice((1, -1))
        self.turning = 1.0                  # 0 to 1 through a turn
        self.tail = random.uniform(0, TAIL_FRAMES)
        self.pause = 0.0

        # its shadow on the sand below it
        w = int(self.length * 0.9)
        yy, xx = np.mgrid[0:max(2, w // 5), 0:w].astype(np.float32)
        d = ((xx - w / 2) / (w / 2)) ** 2 + ((yy - w / 10) / (w / 10)) ** 2
        rgba = np.zeros(xx.shape + (4,), dtype=np.uint8)
        rgba[..., 3] = (np.clip(1 - d, 0, 1) ** 2 * 120).astype(np.uint8)
        self.shadow = pygame.image.frombuffer(rgba.tobytes(), (w, xx.shape[0]), "RGBA").convert_alpha()

    def newTarget(self, night=False):
        if night:
            return random.uniform(150, W - 150), random.uniform(SAND_TOP - 200, SAND_TOP - 70)
        return random.uniform(120, W - 120), random.uniform(SURFACE + 60, SAND_TOP - 70)

    def update(self, dt, flakes, night):
        speed = self.cruise * (0.35 if night else 1)

        # food first: the nearest flake that is still sinking
        flake = None
        if flakes and not night:
            near = [(math.hypot(f.position[0] - self.x, f.position[1] - self.y), f) for f in flakes if f.landed is None]
            if near:
                distance, flake = min(near, key=lambda pair: pair[0])
                if distance > 900:
                    flake = None

        if flake:
            tx, ty = flake.position
            speed *= 2.2
        elif self.school and not night:
            tx, ty = self.school.x + self.offset[0], self.school.y + self.offset[1]
        else:
            tx, ty = self.target
            if math.hypot(tx - self.x, ty - self.y) < 40:
                self.target = self.newTarget(night)
                self.pause = random.uniform(0, 3 if not night else 8)

        if self.pause > 0 and not flake:
            self.pause -= dt
            speed *= 0.15

        dx, dy = tx - self.x, ty - self.y
        distance = math.hypot(dx, dy) or 1
        wantX, wantY = dx / distance * speed, dy / distance * speed * 0.6
        ease = min(1.0, dt * 1.4)
        self.vx += (wantX - self.vx) * ease
        self.vy += (wantY - self.vy) * ease
        self.x += self.vx * dt
        self.y = max(SURFACE + 30, min(SAND_TOP - 30, self.y + self.vy * dt))

        if (self.vx > 8 and self.facing < 0) or (self.vx < -8 and self.facing > 0):
            self.facing = -self.facing
            self.turning = 0.0
        self.turning = min(1.0, self.turning + dt / 0.35)
        self.tail = (self.tail + dt * (2.5 + math.hypot(self.vx, self.vy) / 12)) % TAIL_FRAMES

        # a bite of a flake that is right at its mouth
        if flake:
            mouth = (self.x + self.facing * self.length * 0.45, self.y)
            fx, fy = flake.position
            if math.hypot(fx - mouth[0], fy - mouth[1]) < 18:
                flakes.remove(flake)

    # The shadow on the sand, fainter the higher the fish is above it
    def drawShadow(self, surface):
        ground = SAND_TOP + 25 + (1 - self.depth) * 140
        faint = 1 - (ground - self.y) / 700
        if faint > 0.05:
            self.shadow.set_alpha(int(255 * faint))
            surface.blit(self.shadow, self.shadow.get_rect(center=(self.x, ground)))

    def draw(self, surface):
        frames = self.right if self.facing > 0 else self.left
        frame = int(self.tail) % TAIL_FRAMES
        image = frames[frame]

        # nose up when rising, down when sinking
        tilt = max(-18, min(18, math.degrees(math.atan2(-self.vy, abs(self.vx) + 25)))) * self.facing
        if abs(tilt) >= 2 and self.turning >= 1:
            image = pygame.transform.rotozoom(image, round(tilt), 1)

        if self.turning < 1:
            # seen edge on halfway through a turn
            squash = abs(math.cos(math.pi * self.turning))
            frames = self.left if self.facing > 0 else self.right
            if self.turning >= 0.5:
                frames = self.right if self.facing > 0 else self.left
            image = frames[int(self.tail) % TAIL_FRAMES]
            image = pygame.transform.scale(image, (max(2, int(image.get_width() * max(0.15, squash))), image.get_height()))
        surface.blit(image, image.get_rect(center=(self.x, self.y)))


class School:
    """Where a school of small fish is heading; each one keeps its own place in it."""

    def __init__(self):
        self.x, self.y = W / 2, H / 2
        self.target = (W / 2, H / 2)

    def update(self, dt):
        dx, dy = self.target[0] - self.x, self.target[1] - self.y
        distance = math.hypot(dx, dy)
        if distance < 60:
            self.target = (random.uniform(250, W - 250), random.uniform(150, SAND_TOP - 160))
        else:
            self.x += dx / distance * 70 * dt
            self.y += dy / distance * 40 * dt


##==================================================================
## THE SCREEN
##==================================================================

class AquariumScreen(scr.Screen):

    name = "AQUARIUM"
    hasSound = True

    def soundList(self):
        return [(self.bubbling, 1.0), (self.plip, 1.0)]

    def setSound(self, on):
        if not on:
            self.leave()

    def start(self):
        rng = np.random.default_rng(31)
        self.tank = drawTank()
        self.rays = [(drawRay(int(rng.uniform(90, 180)), rng), rng.uniform(100, W - 300), rng.uniform(0, 6.3))
                     for _ in range(4)]

        self.school = School()
        self.fish = []
        for kind, count, length in STOCK:
            if kind == "tetra":
                frames = drawFish(kind, length, 0.15)
                self.fish += [Fish(kind, length, 0.15, frames, self.school) for _ in range(count)]
            else:
                for _ in range(count):
                    depth = rng.uniform(0, 0.8)
                    self.fish.append(Fish(kind, length, depth, drawFish(kind, length * (1 - 0.4 * depth), depth * 0.6)))

        greens = [(40, 130, 60), (70, 150, 50), (30, 110, 70), (90, 160, 70), (110, 140, 50), (50, 120, 90)]
        self.backPlants = [Plant(x, SAND_TOP + rng.uniform(-5, 15), rng.uniform(300, 560), random.choice(greens), True)
                           for x in rng.uniform(60, W - 60, 10)]
        self.frontPlants = [Plant(x, H - rng.uniform(40, 120), rng.uniform(260, 460), random.choice(greens), False)
                            for x in (90, 230, 1720, 1850, 640)]

        self.bubbles = []
        self.flakes = []
        self.night = None
        self.nightTint = pygame.Surface((W, H))
        self.nightTint.fill(NIGHT)
        self.lastTicks = pygame.time.get_ticks()
        self.bubbling = makeBubbling() if SOUND else None
        self.plip = makePlip() if SOUND else None
        self.bubbleChannel = None
        self.caustic = np.zeros((40, 192), dtype=np.float32)
        self.causticImage = None
        self.frame = 0


    def enter(self):
        self.lastTicks = pygame.time.get_ticks()


    def leave(self):
        if self.bubbleChannel:
            self.bubbleChannel.stop()
            self.bubbleChannel = None


    def handleEvent(self, event):
        if event.type == scr.OK_PRESSED or (event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_SPACE)):
            middle = random.uniform(300, W - 300)
            for _ in range(FOOD_FLAKES):
                self.flakes.append(Flake(middle + random.gauss(0, 90)))
            if self.plip and self.soundOn:
                self.plip.play()


    def update(self, visible):
        if not visible:
            return

        ticks = pygame.time.get_ticks()
        dt = min(0.1, (ticks - self.lastTicks) / 1000)
        self.lastTicks = ticks
        t = ticks / 1000
        self.t = t

        night = ClockScreen.quietTime(datetime.datetime.now())
        if night != self.night:
            self.night = night
            for fish in self.fish:
                fish.target = fish.newTarget(night)

        # the sound of the bubbles, except at night or with the sound off
        if self.bubbling:
            quiet = night or not self.soundOn
            if not quiet and (self.bubbleChannel is None or not self.bubbleChannel.get_busy()):
                self.bubbleChannel = self.bubbling.play(loops=-1)
            elif quiet and self.bubbleChannel:
                self.bubbleChannel.fadeout(1000)
                self.bubbleChannel = None

        self.school.update(dt)
        for fish in self.fish:
            fish.update(dt, self.flakes, night)

        if random.random() < dt * 9:
            self.bubbles.append(Bubble(1675 + random.uniform(-12, 12), 935))
        self.bubbles = [b for b in self.bubbles if b.update(dt)]
        self.flakes = [f for f in self.flakes if f.update(dt, t)]


    # Sunlight rippling on the sand: bright wavy lines that drift and change (worked out every third frame)
    def drawCaustics(self, surface, t):
        self.frame += 1
        if self.causticImage is None or self.frame % 3 == 0:
            self.causticImage = self.makeCaustics(t)
        surface.blit(self.causticImage, (0, SAND_TOP - 20), special_flags=pygame.BLEND_RGB_ADD)


    def makeCaustics(self, t):
        h, w = self.caustic.shape
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        a = np.sin(xx * 0.21 + t * 0.9 + 1.7 * np.sin(yy * 0.33 + t * 0.6))
        b = np.sin(xx * 0.13 - yy * 0.25 - t * 0.7 + 1.3 * np.sin(xx * 0.09 + t * 0.4))
        light = np.clip(1 - np.abs(a + b) * 1.4, 0, 1) ** 3 * 70
        light *= np.linspace(0.6, 1, h)[:, None]
        rgb = np.repeat(light.T[:, :, None], 3, axis=2).astype(np.uint8)
        return pygame.transform.smoothscale(pygame.surfarray.make_surface(rgb), (W, H - SAND_TOP + 30))


    def draw(self, surface):
        t = getattr(self, "t", 0)
        surface.blit(self.tank, (0, 0))

        if not self.night:
            for strengths, x, phase in self.rays:
                ray = strengths[int((0.5 + 0.5 * math.sin(t * 0.4 + phase)) * (len(strengths) - 0.01))]
                surface.blit(ray, (x + 30 * math.sin(t * 0.1 + phase), 0), special_flags=pygame.BLEND_RGB_ADD)
            self.drawCaustics(surface, t)

        if not self.night:
            for fish in self.fish:
                fish.drawShadow(surface)

        for plant in self.backPlants:
            plant.draw(surface, t)

        for fish in sorted(self.fish, key=lambda f: -f.depth):
            fish.draw(surface)

        for flake in self.flakes:
            flake.draw(surface)
        for plant in self.frontPlants:
            plant.draw(surface, t)
        for bubble in self.bubbles:
            bubble.draw(surface)

        # the moving glints of light on the underside of the surface
        for i in range(3):
            points = [(x, SURFACE - 6 + 4 * math.sin(x / (70 + i * 23) + t * (1.2 + i * 0.3)) + i * 4)
                      for x in range(0, W + 40, 40)]
            pygame.draw.lines(surface, (190, 235, 245), False, points, 2)

        if self.night:
            surface.blit(self.nightTint, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
