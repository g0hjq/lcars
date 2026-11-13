"""
viewscreen.py

The main viewscreen on the bridge, set in its frame in the bulkhead, with running lights
chasing round it and a console below: stars drift slowly past at impulse, with a planet or a nebula
ahead. Press OK (or Enter), or wait a few minutes, and the ship goes to warp: the stars
stretch into streaks, there is a flash, and they stream past. A while later it drops out
of warp somewhere new, beside another planet or nebula. Pressing OK at warp drops out at once.

The planets and nebulae are made up by the program, each one different: gas giants (some
with rings), Earth-like worlds with seas and clouds, deserts, ice worlds and lava worlds,
each with a made-up name. The next one is made in the background while the ship is at warp.

The bridge hums quietly, and the consoles chirp now and then; going to warp powers up with a
rising sweep before the jump, and dropping out winds down again.
"""

import math
import os
import random
import threading
import numpy as np
import pygame
import fonts
import screens as scr
import synth

##==================================================================
## CONFIGURATION
##==================================================================

SOUND = True
SOUND_VOLUME = 0.5              # 0 to 1
AUTO_WARP_MINUTES = (3, 7)      # at impulse, it goes to warp by itself after between these many minutes (None: only with OK)
WARP_SECONDS = (12, 30)         # and stays at warp for between these many seconds

W, H = scr.SCREEN_WIDTH, scr.SCREEN_HEIGHT
VIEW = pygame.Rect(150, 64, 1620, 800)     # the screen itself, inside its frame
CORNER = 46                     # how round its corners are
BEZEL = 30                      # how wide the metal frame round it is
CX, CY = VIEW.center
STARS = 650
FOCAL = 640                     # how far the stars are spread: bigger looks more zoomed in
IMPULSE_SPEED = 0.025           # how fast the stars come towards you, in their units a second...
WARP_SPEED = 2.2                # ...and at warp
ENGAGE_SECONDS = 1.6            # the stars stretch for this long before the jump to warp
DROP_SECONDS = 1.1              # and slow for this long when dropping out of warp

ORANGE = (255, 153, 0)
PEACH = (255, 160, 90)
LILAC = (204, 153, 255)
ICE_BLUE = (153, 204, 255)
BUTTERSCOTCH = (255, 204, 102)
BLUE = (132, 132, 255)
AMBER_LIGHT = (255, 170, 60)    # the running lights at impulse...
BLUE_LIGHT = (110, 175, 255)    # ...and at warp
CHIRP_SECONDS = (5, 16)         # the consoles chirp every so often, between these many seconds apart


##==================================================================
## THE SOUNDS
##==================================================================

# Noise that repeats exactly after its length, so that it can be played round and round,
# mostly made of frequencies between low and high
def loopNoise(seconds, low, high, rng):
    n = int(seconds * synth.SAMPLE_RATE)
    freqs = np.fft.rfftfreq(n, 1 / synth.SAMPLE_RATE)
    spectrum = np.where((freqs > low) & (freqs < high), 1.0, 0.0) * np.exp(1j * rng.uniform(0, 2 * np.pi, len(freqs)))
    noise = np.fft.irfft(spectrum, n)
    return noise / np.max(np.abs(noise))


# The low hum of the bridge: the engines far below, a slow swell, and the hiss of the air,
# to play round and round (louder at warp)
def engineHum(rng):
    seconds = 8.0
    t = synth.times(seconds)
    hum = sum(a * np.sin(2 * np.pi * f * t) for f, a in ((50, 1.0), (75, 0.35), (100, 0.55), (150, 0.2), (200, 0.08)))
    hum *= 0.82 + 0.18 * np.sin(2 * np.pi * 0.25 * t)
    rumble = loopNoise(seconds, 35, 160, rng)
    air = loopNoise(seconds, 2000, 7000, rng)
    return hum + 0.45 * rumble + 0.05 * air


# A console chirping: two to four quick, bright notes
def chirp(rng):
    notes = rng.choice([1046.5, 1174.7, 1318.5, 1568.0, 1760.0, 2093.0], size=rng.integers(2, 5))
    length = 0.075
    sound = np.zeros(int(synth.SAMPLE_RATE * (length * len(notes) + 0.1)))
    t = synth.times(length)
    for i, f in enumerate(notes):
        note = np.sin(2 * np.pi * f * t + 0.6 * np.sin(2 * np.pi * f * 2 * t)) * np.minimum(1, t / 0.004) * np.exp(-t / 0.035)
        synth.mixIn(sound, note, i * length)
    return sound


# Going to warp: the engines power up in a rising sweep, then the jump: a deep boom, a
# crack of noise, and a bright shimmer that fades
def engage(rng):
    seconds = 4.2
    t = synth.times(seconds)
    rising = np.clip(t / ENGAGE_SECONDS, 0, 1)
    before = t < ENGAGE_SECONDS
    pitch = 140 * (900 / 140) ** (rising ** 1.6)
    phase = 2 * np.pi * np.cumsum(pitch) / synth.SAMPLE_RATE
    sweep = (np.sin(phase) + 0.5 * np.sin(2 * phase) + 0.25 * np.sin(3 * phase)) * rising ** 1.5 * before
    sweep *= 0.75 + 0.25 * np.sin(2 * np.pi * (6 + 20 * rising) * t)

    rush = synth.noise(seconds, rng)
    rush = synth.smooth(rush, 30) * (1 - rising) + synth.smooth(rush, 3) * rising
    rush *= rising ** 2 * np.exp(-np.clip(t - ENGAGE_SECONDS, 0, None) / 0.35)

    after = np.clip(t - ENGAGE_SECONDS, 0, None)
    jumped = t >= ENGAGE_SECONDS
    boom = np.sin(2 * np.pi * (55 * after - 10 * after ** 2)) * np.exp(-after / 0.6) * jumped
    crack = synth.noise(seconds, rng) * np.exp(-after / 0.08) * jumped
    shimmer = sum(np.sin(2 * np.pi * f * t) for f in (1318.5, 1760, 2217.5, 2637)) / 4
    shimmer *= np.exp(-after / 1.0) * jumped * (0.6 + 0.4 * np.sin(2 * np.pi * 9 * t))
    return sweep * 0.55 + rush * 0.6 + boom * 1.3 + crack * 0.5 + shimmer * 0.3


# Dropping out of warp: the engines wind down in a falling sweep, with a rush of air
def dropOut(rng):
    seconds = 1.8
    t = synth.times(seconds)
    falling = np.clip(t / 1.2, 0, 1)
    pitch = 900 * (120 / 900) ** (falling ** 0.7)
    phase = 2 * np.pi * np.cumsum(pitch) / synth.SAMPLE_RATE
    sweep = (np.sin(phase) + 0.4 * np.sin(2 * phase)) * np.exp(-t / 0.7)
    rush = synth.noise(seconds, rng)
    rush = synth.smooth(rush, 3) * (1 - falling) + synth.smooth(rush, 40) * falling
    return sweep * 0.6 + rush * np.exp(-t / 0.4) * 0.8


def makeSounds():
    if not SOUND:
        return None
    rng = np.random.default_rng(14)
    hum = synth.makeSound(engineHum(rng), SOUND_VOLUME)
    if hum is None:
        return None
    sounds = {"hum": hum, "engage": synth.makeSound(engage(rng), SOUND_VOLUME),
              "drop": synth.makeSound(dropOut(rng), SOUND_VOLUME * 0.8)}
    for i in range(6):
        sounds[f"chirp{i}"] = synth.makeSound(chirp(rng), SOUND_VOLUME * 0.35)
    return sounds


##==================================================================
## MADE-UP PLANETS AND NEBULAE
##==================================================================

SYLLABLES = ["ka", "vor", "tel", "ri", "xa", "mon", "dra", "the", "lo", "zu", "ben", "qua", "sar", "ion",
             "cep", "nar", "ve", "ost", "ul", "py", "gor", "ae", "tis", "rak"]


def madeUpName(rng):
    name = "".join(rng.choice(SYLLABLES) for _ in range(rng.integers(2, 4))).capitalize()
    return f"{name} {rng.choice(['I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'Prime', 'Minor'])}"


# Smooth random hills over the surface of a sphere: waves in random directions in 3D, so
# there is no seam anywhere. Several layers of them, each finer and fainter than the last.
def sphereNoise(x, y, z, rng, scale=2.0, layers=4):
    total = np.zeros_like(x)
    amplitude = 1.0
    for _ in range(layers):
        for _ in range(6):
            d = rng.normal(size=3)
            d /= np.linalg.norm(d)
            total += amplitude * np.sin((x * d[0] + y * d[1] + z * d[2]) * scale * rng.uniform(0.7, 1.3) + rng.uniform(0, 6.3))
        amplitude *= 0.5
        scale *= 2.1
    return total / 4


def ramp(value, stops):
    """Colours along value: stops are (value, (r, g, b)), in order."""
    xs = [s[0] for s in stops]
    out = np.zeros(value.shape + (3,), dtype=np.float32)
    for i in range(3):
        out[..., i] = np.interp(value, xs, [s[1][i] for s in stops])
    return out


# A made-up planet: (picture with see-through corners as an RGBA array, kind, name)
def makePlanet(rng):
    kind = rng.choice(["gas giant", "class M", "desert", "ice", "lava"], p=[0.3, 0.25, 0.2, 0.15, 0.1])
    diameter = int(rng.uniform(320, 600))
    rings = kind == "gas giant" and rng.random() < 0.55
    size = int(diameter * (2.3 if rings else 1.15))
    half = size / 2
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    u, v = (xx - half) / (diameter / 2), (yy - half) / (diameter / 2)
    r2 = u * u + v * v
    inside = r2 < 1
    z = np.sqrt(np.clip(1 - r2, 0, 1))

    # turn the planet a little, so its bands and poles are tilted
    tilt = rng.uniform(-0.5, 0.5)
    x, y = u * math.cos(tilt) - v * math.sin(tilt), u * math.sin(tilt) + v * math.cos(tilt)

    glow = np.zeros_like(u)
    if kind == "gas giant":
        hue = rng.choice([[(200, 150, 100), (230, 200, 160), (150, 90, 60)], [(120, 160, 210), (200, 220, 240), (60, 90, 150)],
                          [(210, 190, 120), (240, 230, 190), (170, 120, 70)], [(190, 120, 150), (230, 190, 200), (120, 70, 110)]])
        bands = np.sin(y * rng.uniform(7, 14) + 1.4 * sphereNoise(x, y, z, rng, 1.5, 3))
        colour = ramp(bands, [(-1, hue[2]), (0, hue[0]), (1, hue[1])])
        air = np.array(hue[1], dtype=np.float32)
    elif kind == "class M":
        height = sphereNoise(x, y, z, rng, 1.8, 5)
        sea = rng.uniform(-0.1, 0.25)
        colour = ramp(height, [(-2, (10, 30, 90)), (sea, (30, 80, 160)), (sea + 0.02, (190, 180, 130)),
                               (sea + 0.15, (60, 120, 50)), (sea + 0.6, (110, 100, 70)), (2, (230, 230, 230))])
        colour = np.where((np.abs(y) > 0.8 + 0.08 * sphereNoise(x, y, z, rng, 3.0, 2))[..., None], np.array([235, 240, 250], dtype=np.float32), colour)
        clouds = np.clip(sphereNoise(x * 1.3, y * 2.2, z, rng, 2.2, 4) - 0.2, 0, 1)[..., None]
        colour = colour * (1 - clouds) + 245 * clouds
        air = np.array([120, 170, 255], dtype=np.float32)
    elif kind == "desert":
        height = sphereNoise(x, y, z, rng, 2.0, 5)
        tones = rng.choice([[(120, 60, 30), (200, 120, 60), (240, 200, 140)], [(90, 80, 70), (160, 150, 130), (220, 210, 190)],
                            [(140, 50, 30), (210, 110, 70), (250, 170, 120)]])
        colour = ramp(height, [(-1.5, tones[0]), (0, tones[1]), (1.5, tones[2])])
        air = np.array(tones[2], dtype=np.float32) * 0.8
    elif kind == "ice":
        height = sphereNoise(x, y, z, rng, 2.0, 5)
        colour = ramp(height, [(-1.5, (150, 180, 210)), (0, (215, 230, 245)), (1.5, (250, 252, 255))])
        cracks = np.exp(-np.abs(sphereNoise(x, y, z, rng, 3.0, 3)) * 14)[..., None]
        colour = colour * (1 - 0.6 * cracks) + np.array([40, 90, 160]) * 0.6 * cracks
        air = np.array([200, 230, 255], dtype=np.float32)
    else:
        height = sphereNoise(x, y, z, rng, 2.2, 5)
        colour = ramp(height, [(-1.5, (25, 18, 16)), (0, (55, 40, 32)), (1.5, (90, 70, 55))])
        glow = np.exp(-np.abs(sphereNoise(x, y, z, rng, 2.5, 3)) * 9)
        air = np.array([255, 120, 40], dtype=np.float32) * 0.6

    # lit from one side, with a soft edge between day and night, and the air glowing at the rim
    light = rng.normal(size=3)
    light[2] = abs(light[2]) * 0.6
    light /= np.linalg.norm(light)
    lit = np.clip((u * light[0] + v * light[1] + z * light[2] + 0.12) / 0.5, 0, 1) ** 1.2
    rgb = colour * (0.03 + 0.97 * lit)[..., None]
    rim = ((1 - z) ** 3 * lit)[..., None] * air * 0.7
    rgb = rgb + rim + (glow[..., None] * np.array([255, 120, 30]) * (1.2 - lit[..., None]))
    alpha = np.clip((1 - np.sqrt(r2)) * diameter / 2 + 0.5, 0, 1)

    # the haze of air just outside the edge, on the lit side
    distance = np.sqrt(r2)
    lightSide = np.clip((u * light[0] + v * light[1]) / np.maximum(distance, 1e-3) + 0.3, 0, 1)
    halo = np.exp(-np.clip(distance - 1, 0, None) / 0.035) * (distance >= 1) * lightSide * (0.2 if kind == "lava" else 0.55)
    rgb = np.where(inside[..., None], rgb, air * 1.1)
    alpha = np.maximum(alpha, halo)

    if rings:
        lean = rng.uniform(0.15, 0.35)
        ru = u * math.cos(tilt) + v * math.sin(tilt)
        rv = (-u * math.sin(tilt) + v * math.cos(tilt)) / lean
        rr = np.sqrt(ru * ru + rv * rv)
        band = (rr > 1.35) & (rr < 2.2)
        shade = (0.55 + 0.45 * np.sin(rr * 40) * np.sin(rr * 9 + 1)) * np.clip((2.2 - rr) * 6, 0, 1) * np.clip((rr - 1.35) * 6, 0, 1)
        ringColour = np.array(hue[1], dtype=np.float32) * (0.5 + 0.6 * shade)[..., None]
        ringAlpha = band * shade * 0.85
        front = rv > 0                          # the near half passes in front of the planet
        show = ringAlpha * (front | ~inside)
        rgb = rgb * (1 - show[..., None]) + ringColour * show[..., None]
        alpha = np.maximum(alpha, show)

    rgba = np.dstack((np.clip(rgb, 0, 255), alpha * 255)).astype(np.uint8)
    name = f"{madeUpName(rng)}   {kind.upper()}" if kind != "class M" else f"{madeUpName(rng)}   CLASS M PLANET"
    return rgba, name


# A made-up nebula filling the view: glowing clouds of gas in two colours, as an RGB array to add
def makeNebula(rng):
    w, h = 320, 180
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    x, y = xx / w * 3, yy / w * 3
    z = np.zeros_like(x)
    density = np.clip(sphereNoise(x, y, z, rng, 2.0, 5) + rng.uniform(-0.2, 0.3), 0, None) ** 1.6
    swirl = np.clip(sphereNoise(x + 3, y, z, rng, 3.0, 4) * 0.5 + 0.5, 0, 1)
    colours = rng.choice([[(255, 80, 160), (80, 140, 255)], [(255, 140, 50), (200, 60, 120)], [(80, 220, 200), (90, 80, 255)],
                          [(255, 200, 90), (255, 70, 60)]])
    a, b = np.array(colours[0], dtype=np.float32), np.array(colours[1], dtype=np.float32)
    rgb = (a * swirl[..., None] + b * (1 - swirl[..., None])) * np.clip(density, 0, 1.5)[..., None] * 0.7
    name = f"{madeUpName(rng)} NEBULA"
    return np.clip(rgb, 0, 255).astype(np.uint8), name


# A new place to arrive at: (kind, array, name), made on a background thread
def makeDestination():
    rng = np.random.default_rng()
    if rng.random() < 0.25:
        rgb, name = makeNebula(rng)
        return "nebula", rgb, name
    rgba, name = makePlanet(rng)
    return "planet", rgba, name


##==================================================================
## THE FAR STARS (drawn once)
##==================================================================

def drawSky():
    rng = np.random.default_rng(3)
    # a faint band of the galaxy across the sky, worked out at a quarter of the size and enlarged
    yy, xx = np.mgrid[0:H // 4, 0:W // 4].astype(np.float32) * 4
    band = np.exp(-((yy - 0.35 * xx - 200) / 260) ** 2)
    cloud = np.clip(sphereNoise(xx / 500, yy / 500, np.zeros_like(xx), rng, 2.0, 4) * 0.5 + 0.6, 0, 1)
    rgb = (band * cloud)[..., None] * np.array([26, 22, 36], dtype=np.float32)
    small = pygame.surfarray.make_surface(np.clip(rgb, 0, 255).astype(np.uint8).transpose(1, 0, 2))
    surface = pygame.transform.smoothscale(small, (W, H))
    for _ in range(2200):
        b = rng.uniform(40, 200) ** 1.0
        tint = rng.choice([(1, 1, 1), (0.8, 0.9, 1), (1, 0.9, 0.75)])
        surface.set_at((int(rng.uniform(0, W)), int(rng.uniform(0, H))), tuple(int(b * c) for c in tint))
    return surface


# How far each point is outside the screen's rounded rectangle (minus: inside it), and which
# way is outwards from it
def outsideScreen(xx, yy):
    cx, cy = VIEW.center
    qx = np.abs(xx - cx) - (VIEW.width / 2 - CORNER)
    qy = np.abs(yy - cy) - (VIEW.height / 2 - CORNER)
    ox, oy = np.maximum(qx, 0), np.maximum(qy, 0)
    distance = np.sqrt(ox * ox + oy * oy) + np.minimum(np.maximum(qx, qy), 0) - CORNER
    length = np.maximum(np.sqrt(ox * ox + oy * oy), 1e-3)
    nx = np.where(ox > 0, ox / length, np.where(qx > qy, 1.0, 0.0)) * np.sign(xx - cx)
    ny = np.where(oy > 0, oy / length, np.where(qy >= qx, 1.0, 0.0)) * np.sign(yy - cy)
    return distance, nx, ny


# The bulkhead round the screen: warm grey wall panels, the rounded metal bezel with a dark
# lip where it meets the screen, and the console below. See-through over the screen itself.
def drawFrame():
    rng = np.random.default_rng(8)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    distance, nx, ny = outsideScreen(xx, yy)

    # the wall: panels with seams, lit from above
    wall = np.array([92, 84, 76], dtype=np.float32) * (1.05 - 0.4 * yy / H)[..., None]
    seams = ((xx % 214) < 3) | (np.abs(yy - 30) < 2)
    wall[seams] *= 0.55
    wall *= (1 + rng.normal(0, 0.025, (H, W)))[..., None]

    # the bezel: a rounded metal rim, lit from above, and a dark lip at its inner edge
    t = np.clip(distance / BEZEL, 0, 1)
    slope = np.cos(np.pi * t)                       # facing in at the inside, out at the outside
    lit = 0.5 - 0.42 * slope * ny + 0.1 * np.sin(np.pi * t)
    bezel = np.array([120, 118, 122], dtype=np.float32) * lit[..., None]
    bezel += (np.exp(-((t - 0.3) / 0.05) ** 2) * np.clip(-ny, 0, 1) * 90)[..., None]
    lip = np.clip(1 - distance / 6, 0, 1)
    bezel *= (1 - 0.85 * lip)[..., None]

    inBezel = (distance < BEZEL)[..., None]
    rgb = np.where(inBezel, bezel, wall)

    # a shadow on the wall round the bezel
    rgb *= (1 - 0.45 * np.exp(-np.clip(distance - BEZEL, 0, None) / 14) * (distance > BEZEL))[..., None]

    # the console below
    console = yy > VIEW.bottom + BEZEL + 30
    rgb[console] = np.array([34, 33, 38], dtype=np.float32) * (1 + rng.normal(0, 0.02, int(console.sum())))[:, None]
    top = int(VIEW.bottom + BEZEL + 30)
    rgb[top:top + 3] = (110, 108, 112)

    alpha = np.clip(distance + 0.5, 0, 1) * 255
    rgba = np.dstack((np.clip(rgb, 0, 255), alpha)).astype(np.uint8)
    frame = pygame.image.frombuffer(rgba.tobytes(), (W, H), "RGBA").convert_alpha()

    # the console's fixed LCARS panels
    font = lcarsFont(22)
    y = top + 24
    pygame.draw.rect(frame, ORANGE, (40, y, 210, 58), border_top_left_radius=29, border_bottom_left_radius=29)
    pygame.draw.rect(frame, LILAC, (W - 250, y, 210, 58), border_top_right_radius=29, border_bottom_right_radius=29)
    for i, (label, colour) in enumerate((("HELM", BUTTERSCOTCH), ("OPS", PEACH), ("NAV", BLUE), ("SCI", ICE_BLUE))):
        x = W - 760 + i * 122
        pygame.draw.rect(frame, colour, (x, y - 4, 112, 30))
        image = font.render(label, True, (0, 0, 0))
        frame.blit(image, (x + 6, y - 2))

    # a row of thin LCARS bars along the bottom of the console
    x, y = 40, top + 104
    for width, colour in ((300, PEACH), (90, LILAC), (520, BUTTERSCOTCH), (60, ORANGE), (240, BLUE), (420, ICE_BLUE),
                          (W - 40 - 40 - 300 - 90 - 520 - 60 - 240 - 420 - 6 * 10, PEACH)):
        pygame.draw.rect(frame, colour, (x, y, width, 18), border_radius=9 if colour in (PEACH,) else 0)
        x += width + 10
    return frame, top


# A running light at each brightness, in a colour: a little lit capsule with a soft glow round it
def lightPictures(colour, steps=8):
    pictures = []
    for step in range(steps):
        b = step / (steps - 1)
        w, h = 34, 18
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        d = np.sqrt(((xx - w / 2) / 9) ** 2 + ((yy - h / 2) / 3.2) ** 2)
        core = np.clip(1.5 - d, 0, 1)
        glow = np.exp(-d * 0.9) * 0.6
        level = np.clip(core * (0.25 + 0.75 * b) + glow * b, 0, 1)
        rgb = np.array(colour, dtype=np.float32) * level[..., None] + 255 * (core * b * 0.5)[..., None]
        rgba = np.dstack((np.clip(rgb, 0, 255), np.clip(level * 255 + core * 120, 0, 255))).astype(np.uint8)
        pictures.append(pygame.image.frombuffer(rgba.tobytes(), (w, h), "RGBA").convert_alpha())
    return pictures


def lcarsFont(size):
    path = os.path.join(fonts.FONT_FOLDER, fonts.FONT_FILE_BOLD)
    try:
        return pygame.font.Font(path, size)
    except (pygame.error, OSError):
        return pygame.font.SysFont("arial", size, bold=True)


##==================================================================
## THE SCREEN
##==================================================================

class ViewscreenScreen(scr.Screen):

    name = "VIEWSCREEN"
    hasSound = True

    def soundList(self):
        return [(s, 1.0) for s in (self.sounds or {}).values()]

    def setSound(self, on):
        if on:
            self.startHum()
        else:
            self.leave()

    def start(self):
        rng = np.random.default_rng()
        self.x = rng.uniform(-2.2, 2.2, STARS).astype(np.float32)
        self.y = rng.uniform(-1.4, 1.4, STARS).astype(np.float32)
        self.z = rng.uniform(0.05, 1, STARS).astype(np.float32)
        self.tint = rng.choice(np.array([(1, 1, 1), (0.8, 0.88, 1), (1, 0.92, 0.8)]), STARS)
        self.sky = drawSky().convert()
        self.font = lcarsFont(30)
        self.smallFont = lcarsFont(24)
        self.flashSurface = pygame.Surface(VIEW.size)
        self.flashSurface.fill((200, 220, 255))
        self.frame, self.consoleTop = drawFrame()
        self.framePieces = [pygame.Rect(0, 0, W, VIEW.top + CORNER), pygame.Rect(0, VIEW.bottom - CORNER, W, H - VIEW.bottom + CORNER),
                            pygame.Rect(0, VIEW.top + CORNER, VIEW.left + 1, VIEW.height - 2 * CORNER),
                            pygame.Rect(VIEW.right - 1, VIEW.top + CORNER, W - VIEW.right + 1, VIEW.height - 2 * CORNER)]
        self.lights = {"amber": lightPictures(AMBER_LIGHT), "blue": lightPictures(BLUE_LIGHT)}
        self.sideLights_ = {k: [pygame.transform.rotate(p, 90) for p in v] for k, v in self.lights.items()}   # upright, for the sides
        across = range(VIEW.left + 70, VIEW.right - 50, 44)
        self.topLights = [(x, VIEW.top - BEZEL // 2) for x in across]
        self.bottomLights = [(x, VIEW.bottom + BEZEL // 2) for x in across]
        down = range(VIEW.top + 80, VIEW.bottom - 60, 60)
        self.sideLights = [(VIEW.left - BEZEL // 2, y) for y in down] + [(VIEW.right + BEZEL // 2, y) for y in down]
        self.readings = []              # the console's changing numbers, and when they last changed
        self.readingsAt = 0
        self.nextChirp = pygame.time.get_ticks() + 4000

        self.state = "impulse"
        self.stateAt = pygame.time.get_ticks()
        self.speed = IMPULSE_SPEED
        self.flash = 0.0
        self.destination = None         # the planet or nebula in view (the first is made in the background)
        self.prepareNext()
        self.nextWarp = self.autoWarpTime()
        self.warpUntil = 0
        self.lastTicks = pygame.time.get_ticks()
        self.sounds = makeSounds()
        self.humChannel = None
        self.label = None


    def autoWarpTime(self):
        if not AUTO_WARP_MINUTES:
            return None
        return pygame.time.get_ticks() + random.uniform(*AUTO_WARP_MINUTES) * 60000


    # Arrive at a new planet or nebula, a little to one side of the middle
    def arrive(self, destination):
        kind, array, name = destination
        if kind == "planet":
            h, w = array.shape[:2]
            image = pygame.image.frombuffer(array.tobytes(), (w, h), "RGBA").convert_alpha()
            x = VIEW.left + random.choice([random.uniform(0.18, 0.35), random.uniform(0.65, 0.82)]) * VIEW.width
            y = VIEW.top + random.uniform(0.32, 0.68) * VIEW.height
        else:
            image = pygame.transform.smoothscale(pygame.surfarray.make_surface(array.transpose(1, 0, 2)), VIEW.size)
            x, y = CX, CY
        self.destination = dict(kind=kind, image=image, name=name, x=x, y=y,
                                drift=(random.uniform(-4, 4), random.uniform(-2, 2)))


    def prepareNext(self):
        def work():
            self.nextDestination = makeDestination()
        self.nextDestination = None
        threading.Thread(target=work, daemon=True).start()


    def play(self, name):
        if self.soundOn and self.sounds and self.sounds.get(name):
            self.sounds[name].play()


    def goToWarp(self):
        self.state, self.stateAt = "engaging", pygame.time.get_ticks()
        self.prepareNext()
        self.play("engage")


    def dropOut(self):
        self.state, self.stateAt = "dropping", pygame.time.get_ticks()
        self.play("drop")


    def enter(self):
        self.lastTicks = pygame.time.get_ticks()
        self.startHum()


    def startHum(self):
        if self.sounds and self.soundOn and not self.humChannel:
            self.humChannel = self.sounds["hum"].play(loops=-1)


    def leave(self):
        if self.humChannel:
            self.humChannel.stop()
            self.humChannel = None


    def handleEvent(self, event):
        if event.type == scr.OK_PRESSED or (event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_SPACE)):
            if self.state == "impulse":
                self.goToWarp()
            elif self.state == "warp":
                self.dropOut()


    def update(self, visible):
        if not visible:
            return

        ticks = pygame.time.get_ticks()
        dt = min(0.1, (ticks - self.lastTicks) / 1000)
        self.lastTicks = ticks
        into = (ticks - self.stateAt) / 1000

        # the stages of a warp jump
        if self.state == "impulse":
            self.speed = IMPULSE_SPEED
            if self.destination is None and self.nextDestination:
                self.arrive(self.nextDestination)
            if self.nextWarp and ticks >= self.nextWarp:
                self.goToWarp()
        elif self.state == "engaging":
            p = min(1.0, into / ENGAGE_SECONDS)
            self.speed = IMPULSE_SPEED + (WARP_SPEED * 0.3) * p ** 3
            if p >= 1:
                self.state, self.stateAt = "warp", ticks
                self.flash = 1.0
                self.warpUntil = ticks + random.uniform(*WARP_SECONDS) * 1000
        elif self.state == "warp":
            self.speed = WARP_SPEED
            if ticks >= self.warpUntil and self.nextDestination:
                self.dropOut()
        elif self.state == "dropping":
            p = min(1.0, into / DROP_SECONDS)
            self.speed = WARP_SPEED * (1 - p) ** 3 + IMPULSE_SPEED
            if p >= 1:
                self.state, self.stateAt = "impulse", ticks
                self.flash = 0.6
                self.arrive(self.nextDestination or makeDestination())
                self.nextWarp = self.autoWarpTime()

        self.flash = max(0.0, self.flash - dt * 2.5)

        # the stars come towards you; one that passes is put back far away
        self.z -= self.speed * dt
        gone = self.z < 0.02
        count = int(gone.sum())
        if count:
            self.x[gone] = np.random.uniform(-2.2, 2.2, count)
            self.y[gone] = np.random.uniform(-1.4, 1.4, count)
            self.z[gone] = np.random.uniform(0.85, 1.0, count)

        if self.destination:
            dx, dy = self.destination["drift"]
            self.destination["x"] += dx * dt
            self.destination["y"] += dy * dt

        # the consoles chirp now and then
        if ticks >= self.nextChirp:
            self.play(f"chirp{random.randrange(6)}")
            self.nextChirp = ticks + random.uniform(*CHIRP_SECONDS) * 1000

        if self.humChannel:
            loud = {"impulse": 0.25, "engaging": 0.25 + 0.6 * min(1, into / ENGAGE_SECONDS), "warp": 0.85,
                    "dropping": 0.85 - 0.6 * min(1, into / DROP_SECONDS)}[self.state]
            self.humChannel.set_volume(loud)

        if self.state == "impulse":
            text = f"IMPULSE      {self.destination['name'].upper()}" if self.destination else "IMPULSE"
        elif self.state == "engaging":
            text = "ENGAGING"
        elif self.state == "warp":
            text = "AT WARP"
        else:
            text = "DROPPING OUT OF WARP"
        if text != self.label:
            self.label = text
            self.labelImage = self.font.render(text, True, (0, 0, 0))


    def draw(self, surface):
        ticks = pygame.time.get_ticks()
        into = (ticks - self.stateAt) / 1000

        # how much of the still sky and the planet are seen: all at impulse, none at warp
        if self.state == "impulse":
            calm = 1.0
        elif self.state == "engaging":
            calm = 1 - min(1, into / ENGAGE_SECONDS)
        elif self.state == "dropping":
            calm = 0.0
        else:
            calm = 0.0

        surface.set_clip(VIEW)
        surface.fill((0, 0, 0), VIEW)
        if calm > 0:
            self.sky.set_alpha(int(255 * calm) if calm < 1 else None)     # see-through only while fading: it is slower
            surface.blit(self.sky, VIEW.topleft, VIEW)
            d = self.destination
            if d:
                if d["kind"] == "nebula":
                    d["image"].set_alpha(int(255 * calm))
                    surface.blit(d["image"], VIEW.topleft, special_flags=pygame.BLEND_RGB_ADD)
                else:
                    image = d["image"]
                    image.set_alpha(int(255 * calm))
                    surface.blit(image, image.get_rect(center=(d["x"], d["y"])))

        self.drawStars(surface, into)

        if self.flash > 0:
            self.flashSurface.set_alpha(int(200 * self.flash))
            surface.blit(self.flashSurface, VIEW.topleft)
        surface.set_clip(None)

        for piece in self.framePieces:
            surface.blit(self.frame, piece.topleft, piece)
        self.drawLights(surface, ticks / 1000)
        self.drawConsole(surface, ticks)


    # The running lights: along the top and the bottom of the frame they chase one way and
    # the other, faster and blue at warp; down the sides they glow and fade slowly
    def drawLights(self, surface, t):
        warp = self.state in ("warp", "engaging")
        pictures = self.lights["blue" if warp else "amber"]
        steps = len(pictures) - 1
        speed = 30 if warp else 9
        tail = 6
        for row, direction in ((self.topLights, 1), (self.bottomLights, -1)):
            count = len(row)
            head = (t * speed) % (count + tail)
            for i, (x, y) in enumerate(row):
                place = i if direction > 0 else count - 1 - i
                behind = head - place
                b = 1 - behind / tail if 0 <= behind < tail else 0.12
                picture = pictures[int(b * steps)]
                surface.blit(picture, picture.get_rect(center=(x, y)))
        for i, (x, y) in enumerate(self.sideLights):
            b = 0.35 + 0.35 * math.sin(t * 1.3 + i * 0.5)
            picture = self.sideLights_[("blue" if warp else "amber")][int(b * steps)]
            surface.blit(picture, picture.get_rect(center=(x, y)))


    # The console below the screen: what the ship is doing, and some busy numbers
    def drawConsole(self, surface, ticks):
        y = self.consoleTop + 24
        width = self.labelImage.get_width() + 40
        pygame.draw.rect(surface, PEACH, (262, y, width, 58))
        surface.blit(self.labelImage, (282, y + 10))

        if ticks - self.readingsAt > 700 or not self.readings:
            self.readingsAt = ticks
            self.readings = [self.smallFont.render(f"{random.randint(0, 9999):04d}", True, colour)
                             for colour in (BUTTERSCOTCH, PEACH, BLUE, ICE_BLUE)]
        for i, image in enumerate(self.readings):
            surface.blit(image, (W - 760 + i * 122 + 6, y + 30))


    # Each star as a dot, or a streak from where it is to where it was a moment ago
    def drawStars(self, surface, into):
        if self.state == "engaging":
            trail = 0.45 * min(1, into / ENGAGE_SECONDS) ** 2
        elif self.state == "warp":
            trail = 0.32
        elif self.state == "dropping":
            trail = 0.32 * (1 - min(1, into / DROP_SECONDS)) ** 2
        else:
            trail = 0.0

        z = self.z
        sx = CX + self.x / z * FOCAL
        sy = CY + self.y / z * FOCAL
        bright = np.clip((1.05 - z) * 300, 0, 255)
        colours = (self.tint * bright[:, None]).astype(int)

        if trail > 0.005:
            tz = np.minimum(z + trail * (0.4 + z), 1.6)
            tx = CX + self.x / tz * FOCAL
            ty = CY + self.y / tz * FOCAL
            blue = np.array([0.8, 0.9, 1.0])
            colours = np.clip(colours * blue * 1.5, 0, 255).astype(int)
            widths = np.where(z < 0.15, 3, np.where(z < 0.4, 2, 1)).tolist()
            colours, tx, ty, sx, sy = colours.tolist(), tx.tolist(), ty.tolist(), sx.tolist(), sy.tolist()
            for i in range(STARS):
                pygame.draw.line(surface, colours[i], (tx[i], ty[i]), (sx[i], sy[i]), widths[i])
        else:
            sizes = np.where(z < 0.2, 3, np.where(z < 0.5, 2, 1)).tolist()
            colours, sx, sy = colours.tolist(), sx.astype(int).tolist(), sy.astype(int).tolist()
            for i in range(STARS):
                if 0 <= sx[i] < W and 0 <= sy[i] < H:
                    surface.fill(colours[i], (sx[i], sy[i], sizes[i], sizes[i]))
