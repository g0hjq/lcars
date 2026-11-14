"""
lavalamp.py

A big lava lamp glowing in a dark room. Blobs of wax warm up at the bottom, swell and rise
slowly through the liquid, cool at the top and sink again, joining and splitting as they
pass one another.

The colours of the wax and the liquid change every hour, fading from one pair to the next,
and the OK button (or Enter) changes them at once.

The wax is worked out as "metaballs": each blob has a field round it, the fields are added
together, and wherever the total is high enough there is wax. That is what makes the blobs
merge so smoothly. It is worked out at a third of the size and enlarged, which is plenty
for something this soft.
"""

import datetime
import math
import random
import numpy as np
import pygame
import screens as scr

##==================================================================
## SETTINGS (they are in settings.py, next to lcars.py)
##==================================================================

W, H = scr.SCREEN_WIDTH, scr.SCREEN_HEIGHT
CX = W // 2
# Its settings are in settings.py (next to lcars.py)
from settings import (
    LAVALAMP_FADE_SECONDS as FADE_SECONDS,
    LAVALAMP_GLOW_SECONDS as GLOW_SECONDS,
    LAVALAMP_BLOBS as BLOBS,
    LAVALAMP_SCALE as SCALE,
    LAVALAMP_PALETTES as PALETTES,
    LAVALAMP_CAP as CAP,
    LAVALAMP_GLASS_TOP as GLASS_TOP,
    LAVALAMP_GLASS_BOTTOM as GLASS_BOTTOM,
    LAVALAMP_BASE as BASE,
    LAVALAMP_SHELF as SHELF,
)


def glassHalfWidth(y):
    """Half the width of the glass this far down it (0 at the top, 1 at the bottom)."""
    t = np.clip(y, 0, 1)
    wide = 72 + 108 * np.sin(np.pi / 2 * np.clip(t / 0.8, 0, 1)) ** 1.3
    return np.where(t < 0.8, wide, 180 - (180 - 126) * np.clip((t - 0.8) / 0.2, 0, 1) ** 1.5)


##==================================================================
## DRAWING THE LAMP (once)
##==================================================================

# A shiny metal part, round like a turned piece: shaded across its width as though curved,
# with bright reflections down it. Returns its picture and where it goes.
def drawMetal(profile, colour):
    top, bottom = profile[0][0], profile[-1][0]
    ys = np.arange(top, bottom)
    halves = np.interp(ys, [p[0] for p in profile], [p[1] for p in profile])
    width = int(halves.max()) + 2
    xs = np.arange(-width, width)
    u = xs[None, :] / halves[:, None]
    inside = np.abs(u) < 1
    z = np.sqrt(np.clip(1 - u * u, 0, 1))
    light = 0.25 + 0.55 * np.clip(-0.55 * u + 0.8 * z, 0, 1)
    shine = np.exp(-((u + 0.45) / 0.09) ** 2) * 0.9 + np.exp(-((u - 0.62) / 0.06) ** 2) * 0.5
    rgb = np.array(colour, dtype=np.float32) * light[..., None] + 255 * shine[..., None]
    alpha = np.clip((1 - np.abs(u)) * halves[:, None], 0, 1) * 255 * inside
    rgba = np.dstack((np.clip(rgb, 0, 255), alpha)).astype(np.uint8)
    image = pygame.image.frombuffer(rgba.tobytes(), (2 * width, len(ys)), "RGBA").convert_alpha()
    return image, (CX - width, top)


# The room: a dark wall, a shelf, and the lamp's metal cap and base
def drawRoom():
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    rng = np.random.default_rng(4)
    wall = np.full((H, W, 3), 14, dtype=np.float32) * (1 + rng.normal(0, 0.05, (H, W)))[..., None]
    shelf = (yy >= SHELF)[..., None]
    rgb = np.where(shelf, np.array([30, 20, 14], dtype=np.float32), wall)
    surface = pygame.surfarray.make_surface(np.clip(rgb, 0, 255).astype(np.uint8).transpose(1, 0, 2))
    pygame.draw.line(surface, (60, 44, 32), (0, SHELF), (W, SHELF), 2)

    # the lamp's shadow on the shelf
    shadow = pygame.Surface((520, 30), pygame.SRCALPHA)
    pygame.draw.ellipse(shadow, (0, 0, 0, 150), shadow.get_rect())
    surface.blit(shadow, (CX - 260, SHELF - 12))
    return surface


# The glow of the lamp on the wall, white, to be tinted with the wax's colour
def drawGlow():
    w, h = W, H
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.sqrt(((xx - w / 2) / 1.3) ** 2 + (yy - 520) ** 2)
    glow = np.exp(-d / 260) * 150
    rgb = np.repeat(glow[..., None], 3, axis=2)
    return pygame.surfarray.make_surface(np.clip(rgb, 0, 255).astype(np.uint8).transpose(1, 0, 2))


# The glass's shape, as an alpha mask the size of the glass, and its shine on top
def drawGlass():
    gh = GLASS_BOTTOM - GLASS_TOP
    gw = 2 * 184
    yy, xx = np.mgrid[0:gh, 0:gw].astype(np.float32)
    half = glassHalfWidth(yy / gh)
    u = (xx - gw / 2) / half
    inside = np.clip((1 - np.abs(u)) * half, 0, 1)

    mask = np.zeros((gh, gw, 4), dtype=np.uint8)
    mask[..., :3] = 255
    mask[..., 3] = (inside * 255).astype(np.uint8)

    # darker towards the edges, as the light passes through more glass; a long reflection down one side
    edge = np.clip(np.abs(u), 0, 1) ** 4 * 140
    shine = np.exp(-((u + 0.55) / 0.07) ** 2) * 90 + np.exp(-((u - 0.72) / 0.04) ** 2) * 40
    shine *= 0.6 + 0.4 * np.sin(np.pi * yy / gh)
    over = np.zeros((gh, gw, 4), dtype=np.float32)
    over[..., :3] = np.where((shine > edge)[..., None], 255.0, 0.0)
    over[..., 3] = np.maximum(shine, edge) * inside
    maskImage = pygame.image.frombuffer(mask.tobytes(), (gw, gh), "RGBA").convert_alpha()
    overImage = pygame.image.frombuffer(np.clip(over, 0, 255).astype(np.uint8).tobytes(), (gw, gh), "RGBA").convert_alpha()
    return maskImage, overImage


##==================================================================
## THE WAX
##==================================================================

class Blob:

    def __init__(self, height, rng):
        self.r = rng.uniform(24, 44)
        self.x = rng.uniform(-60, 60)
        self.y = rng.uniform(0.2, 0.9) * height
        self.vy = 0.0
        self.heat = rng.uniform(0, 1)
        self.wander = rng.uniform(0, 6.3)

    def update(self, dt, height):
        t = self.y / height
        if t > 0.86:
            self.heat = min(1.0, self.heat + dt * 0.08)        # warmed by the bulb at the bottom...
        elif t < 0.15:
            self.heat = max(0.0, self.heat - dt * 0.1)          # ...cooled at the top...
        else:
            self.heat = max(0.0, self.heat - dt * 0.012)        # ...and slowly on the way

        self.vy += (0.45 - self.heat) * 26 * dt                 # warm wax rises, cool wax sinks
        self.vy *= 1 - min(1.0, dt * 0.9)
        self.y = min(height - self.r * 0.4, max(self.r * 0.8, self.y + self.vy * dt))
        self.wander += dt * 0.15
        room = float(glassHalfWidth(t)) - self.r * 0.8
        self.x += math.sin(self.wander) * 6 * dt
        self.x = max(-room, min(room, self.x))


def lerp(a, b, f):
    return tuple(int(x + (y - x) * f) for x, y in zip(a, b))


##==================================================================
## THE SCREEN
##==================================================================

class LavaLampScreen(scr.Screen):

    name = "LAVA LAMP"

    def start(self):
        rng = np.random.default_rng()
        self.room = drawRoom()
        self.metal = [drawMetal(CAP, (176, 176, 186)), drawMetal(BASE, (176, 176, 186))]
        self.glow = drawGlow()
        self.mask, self.shine = drawGlass()

        self.gw, self.gh = self.mask.get_size()
        self.blobs = [Blob(self.gh, rng) for _ in range(BLOBS)]
        yy, xx = np.mgrid[0:self.gh // SCALE, 0:self.gw // SCALE].astype(np.float32)
        self.gx = xx * SCALE - self.gw / 2
        self.gy = yy * SCALE
        self.depth = (self.gy / self.gh)[..., None]

        self.palette = self.hourPalette()
        self.colours = PALETTES[self.palette]
        self.fadeFrom, self.fadeAt = self.colours, -FADE_SECONDS * 1000
        self.litRoom, self.glowColour, self.glowAt = None, None, 0
        self.lastTicks = pygame.time.get_ticks()


    @staticmethod
    def hourPalette():
        return datetime.datetime.now().hour % len(PALETTES)


    def changeTo(self, palette):
        self.fadeFrom = self.colours
        self.fadeAt = pygame.time.get_ticks()
        self.palette = palette


    def enter(self):
        self.lastTicks = pygame.time.get_ticks()


    def handleEvent(self, event):
        if event.type == scr.OK_PRESSED or (event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_SPACE)):
            self.changeTo((self.palette + 1) % len(PALETTES))


    def update(self, visible):
        if not visible:
            return

        ticks = pygame.time.get_ticks()
        dt = min(0.1, (ticks - self.lastTicks) / 1000)
        self.lastTicks = ticks

        # a new hour, new colours
        if datetime.datetime.now().minute == 0 and self.hourPalette() != getattr(self, "hourShown", None):
            self.hourShown = self.hourPalette()
            if self.palette != self.hourShown:
                self.changeTo(self.hourShown)

        fade = min(1.0, (ticks - self.fadeAt) / (FADE_SECONDS * 1000))
        target = PALETTES[self.palette]
        self.colours = (lerp(self.fadeFrom[0], target[0], fade), lerp(self.fadeFrom[1], target[1], fade))

        for blob in self.blobs:
            blob.update(dt, self.gh)


    # The liquid and the wax inside the glass
    def drawWax(self):
        liquid, wax = (np.array(c, dtype=np.float32) for c in self.colours)
        # each blob's field fades smoothly to nothing at 2.2 times its size; a blob moving fast
        # is drawn out a little, as the wax stretches
        field = np.zeros_like(self.gx)
        for blob in self.blobs:
            reach = 2.2 * blob.r
            stretch = 1 / (1 + abs(blob.vy) / 30)
            d2 = ((self.gx - blob.x) ** 2 + ((self.gy - blob.y) * stretch) ** 2) / (reach * reach)
            field += np.clip(1 - d2, 0, 1) ** 3
        field += np.clip(1 - (self.gh - self.gy) / 70, 0, 1) ** 2       # the pool of melted wax at the bottom

        amount = np.clip((field - 0.3) / 0.1, 0, 1)[..., None]

        # lit from the bulb below, so brighter towards the bottom; the wax glows more where it is thicker
        light = 0.4 + 0.8 * self.depth ** 1.4
        thick = (0.6 + 0.55 * np.clip((field - 0.35) / 0.6, 0, 1))[..., None]
        rgb = liquid * 0.72 * light * (1 - amount) + wax * light * thick * amount
        rgb = np.clip(rgb, 0, 255).astype(np.uint8)
        small = pygame.surfarray.make_surface(rgb.transpose(1, 0, 2))
        image = pygame.transform.smoothscale(small, (self.gw, self.gh)).convert_alpha()
        image.blit(self.mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        image.blit(self.shine, (0, 0))
        return image


    def draw(self, surface):
        # the room lit by the lamp's glow, in a colour between the wax's and the liquid's. It
        # is only drawn again when that colour has changed enough to see, and at most every
        # GLOW_SECONDS while the colours fade, as it is slow.
        glowColour = tuple(c // 6 * 6 for c in lerp(self.colours[1], self.colours[0], 0.35))
        ticks = pygame.time.get_ticks()
        if glowColour != self.glowColour and (self.litRoom is None or ticks - self.glowAt > GLOW_SECONDS * 1000):
            self.glowColour, self.glowAt = glowColour, ticks
            tinted = self.glow.copy()
            tinted.fill(glowColour, special_flags=pygame.BLEND_RGB_MULT)
            self.litRoom = self.room.copy()
            self.litRoom.blit(tinted, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
            for image, position in self.metal:
                self.litRoom.blit(image, position)

        surface.blit(self.litRoom, (0, 0))
        surface.blit(self.drawWax(), (CX - self.gw // 2, GLASS_TOP))
