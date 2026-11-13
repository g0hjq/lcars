"""
viewscreen.py

The view from the bridge: stars drifting slowly past at impulse, with a planet or a nebula
ahead. Press OK (or Enter), or wait a few minutes, and the ship goes to warp: the stars
stretch into streaks, there is a flash, and they stream past. A while later it drops out
of warp somewhere new, beside another planet or nebula. Pressing OK at warp drops out at once.

The planets and nebulae are made up by the program, each one different: gas giants (some
with rings), Earth-like worlds with seas and clouds, deserts, ice worlds and lava worlds,
each with a made-up name. The next one is made in the background while the ship is at warp.
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
CX, CY = W / 2, H / 2
STARS = 700
FOCAL = 700                     # how far the stars are spread: bigger looks more zoomed in
IMPULSE_SPEED = 0.025           # how fast the stars come towards you, in their units a second...
WARP_SPEED = 2.2                # ...and at warp
ENGAGE_SECONDS = 1.6            # the stars stretch for this long before the jump to warp
DROP_SECONDS = 1.1              # and slow for this long when dropping out of warp

ORANGE = (255, 153, 0)
PEACH = (255, 160, 90)
LILAC = (204, 153, 255)
ICE_BLUE = (153, 204, 255)


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


# The deep throb of the engines, to play round and round (louder at warp)
def engineHum(rng):
    seconds = 4.0
    t = synth.times(seconds)
    hum = sum(a * np.sin(2 * np.pi * f * t) for f, a in ((55, 1.0), (82.5, 0.4), (110, 0.5), (165, 0.15)))
    hum *= 0.8 + 0.2 * np.sin(2 * np.pi * 0.5 * t)
    return hum + 0.5 * loopNoise(seconds, 30, 300, rng)


# Going to warp: a rising rush, a deep boom at the jump, and a bright shimmer after it
def engage(rng):
    seconds = 4.0
    t = synth.times(seconds)
    rush = synth.noise(seconds, rng)
    rising = np.clip(t / ENGAGE_SECONDS, 0, 1)
    rush = synth.smooth(rush, 30) * (1 - rising) + synth.smooth(rush, 4) * rising
    rush *= rising ** 2 * np.exp(-np.clip(t - ENGAGE_SECONDS, 0, None) / 0.6)

    after = np.clip(t - ENGAGE_SECONDS, 0, None)
    boom = np.sin(2 * np.pi * (60 * after - 12 * after ** 2)) * np.exp(-after / 0.5) * (t >= ENGAGE_SECONDS)
    shimmer = sum(np.sin(2 * np.pi * f * t) for f in (880, 1108.7, 1318.5, 1760)) / 4
    shimmer *= np.exp(-after / 0.9) * (t >= ENGAGE_SECONDS) * (0.6 + 0.4 * np.sin(2 * np.pi * 7 * t))
    return rush * 0.8 + boom * 1.2 + shimmer * 0.35


# Dropping out of warp: a falling rush
def dropOut(rng):
    seconds = 1.8
    t = synth.times(seconds)
    rush = synth.noise(seconds, rng)
    falling = np.clip(t / seconds, 0, 1)
    rush = synth.smooth(rush, 4) * (1 - falling) + synth.smooth(rush, 40) * falling
    tone = np.sin(2 * np.pi * np.cumsum(500 - 380 * falling) / synth.SAMPLE_RATE)
    return (rush + 0.3 * tone) * np.exp(-t / 0.5)


def makeSounds():
    if not SOUND:
        return None
    rng = np.random.default_rng(14)
    hum = synth.makeSound(engineHum(rng), SOUND_VOLUME)
    if hum is None:
        return None
    return {"hum": hum, "engage": synth.makeSound(engage(rng), SOUND_VOLUME),
            "drop": synth.makeSound(dropOut(rng), SOUND_VOLUME * 0.8)}


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

    def start(self):
        rng = np.random.default_rng()
        self.x = rng.uniform(-2.2, 2.2, STARS).astype(np.float32)
        self.y = rng.uniform(-1.4, 1.4, STARS).astype(np.float32)
        self.z = rng.uniform(0.05, 1, STARS).astype(np.float32)
        self.tint = rng.choice(np.array([(1, 1, 1), (0.8, 0.88, 1), (1, 0.92, 0.8)]), STARS)
        self.sky = drawSky().convert()
        self.font = lcarsFont(30)
        self.flashSurface = pygame.Surface((W, H))
        self.flashSurface.fill((200, 220, 255))

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
            x = random.choice([random.uniform(0.15, 0.35), random.uniform(0.65, 0.85)]) * W
            y = random.uniform(0.3, 0.7) * H
        else:
            image = pygame.transform.smoothscale(pygame.surfarray.make_surface(array.transpose(1, 0, 2)), (W, H))
            x, y = W / 2, H / 2
        self.destination = dict(kind=kind, image=image, name=name, x=x, y=y,
                                drift=(random.uniform(-4, 4), random.uniform(-2, 2)))


    def prepareNext(self):
        def work():
            self.nextDestination = makeDestination()
        self.nextDestination = None
        threading.Thread(target=work, daemon=True).start()


    def play(self, name):
        if self.sounds and self.sounds.get(name):
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
        if self.sounds:
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

        surface.fill((0, 0, 0))
        if calm > 0:
            self.sky.set_alpha(int(255 * calm) if calm < 1 else None)     # see-through only while fading: it is slower
            surface.blit(self.sky, (0, 0))
            d = self.destination
            if d:
                if d["kind"] == "nebula":
                    d["image"].set_alpha(int(255 * calm))
                    surface.blit(d["image"], (0, 0), special_flags=pygame.BLEND_RGB_ADD)
                else:
                    image = d["image"]
                    image.set_alpha(int(255 * calm))
                    surface.blit(image, image.get_rect(center=(d["x"], d["y"])))

        self.drawStars(surface, into)

        if self.flash > 0:
            self.flashSurface.set_alpha(int(200 * self.flash))
            surface.blit(self.flashSurface, (0, 0))

        # an LCARS label in the corner
        pygame.draw.rect(surface, ORANGE, (40, H - 74, 26, 40), border_top_left_radius=20, border_bottom_left_radius=20)
        width = self.labelImage.get_width() + 40
        pygame.draw.rect(surface, PEACH, (72, H - 74, width, 40))
        surface.blit(self.labelImage, (92, H - 72))
        pygame.draw.rect(surface, LILAC, (72 + width + 6, H - 74, 40, 40), border_top_right_radius=20, border_bottom_right_radius=20)


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
