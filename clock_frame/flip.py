"""
flip.py

A 1970s flip clock, in a glossy white plastic case on a teak sideboard, in front of
orange and brown wallpaper: two big cards for the hours and the minutes, and a row of small
ones below for the day, the date and the month. When the minute changes, the top half of its
card falls forward over the hinge, showing the next one behind it, and lands with a clack.
"""

import math
import os
import pygame
import numpy as np
import screens as scr
import fonts
import synth
from .common import (Face, screenGrid, smoothstep, waves, toSurface, lighting, bevel, roundedBox,
                     vignette, makeSound)

##==================================================================
## SETTINGS (they are in settings.py, next to lcars.py)
##==================================================================

from settings import (
    FLIP_HOURS_24 as HOURS_24,
    FLIP_SECONDS,
    FLIP_BIG_W as BIG_W,
    FLIP_BIG_H as BIG_H,
    FLIP_BIG_GAP as BIG_GAP,
    FLIP_SMALL_H as SMALL_H,
    FLIP_SMALL_GAP as SMALL_GAP,
    FLIP_SMALL_WIDTHS as SMALL_WIDTHS,
    FLIP_ROW_GAP as ROW_GAP,
    FLIP_MARGIN as MARGIN,
    FLIP_CASE_EDGE as CASE_EDGE,
    FLIP_TOP as TOP,
    FLIP_CORNER as CORNER,
    FLIP_CARD as CARD,
    FLIP_DIGITS as DIGITS,
    FLIP_RECESS as RECESS,
    FLIP_CASE as CASE,
    FLIP_TEAK as TEAK,
    FLIP_TEXT_COLOUR as TEXT_COLOUR,
)

RECESS_W = 2 * BIG_W + BIG_GAP + 2 * MARGIN
RECESS_H = BIG_H + ROW_GAP + SMALL_H + 2 * MARGIN
RECESS_LEFT = (scr.SCREEN_WIDTH - RECESS_W) // 2
RECESS_TOP = TOP + CASE_EDGE
CASE_BOTTOM = RECESS_TOP + RECESS_H + CASE_EDGE


##==================================================================
## THE CARDS
##==================================================================

def flipFont(size):
    try:
        return pygame.font.Font(os.path.join(fonts.FONT_FOLDER, fonts.FONT_FILE_BOLD), size)
    except (pygame.error, OSError):
        return pygame.font.SysFont("arial", size, bold=True)


# A card with text on it, as its top half and its bottom half, each w x h/2. The text is
# made to fill most of the card, keeping its shape.
def cardHalves(text, w, h, font):
    card = pygame.Surface((w, h), pygame.SRCALPHA)
    card.fill((0, 0, 0, 0))
    pygame.draw.rect(card, CARD, card.get_rect(), border_radius=min(CORNER, h // 5))

    ink = font.render(text, True, DIGITS)
    area = ink.get_bounding_rect()
    if area.width and area.height:
        ink = ink.subsurface(area)
        scale = min(0.84 * w / area.width, 0.74 * h / area.height)
        ink = pygame.transform.smoothscale(ink, (round(area.width * scale), round(area.height * scale)))
        card.blit(ink, ink.get_rect(center=(w // 2, h // 2)))

    # lighter at the top of each half, where the light from the window falls on it
    shade = np.ones(h, np.float32)
    half = h // 2
    shade[:half] = 1.12 - 0.2 * np.linspace(0, 1, half)
    shade[half:] = 0.98 - 0.22 * np.linspace(0, 1, h - half)
    pixels = pygame.surfarray.pixels3d(card)
    pixels[:] = np.clip(pixels * shade[None, :, None], 0, 255).astype(np.uint8)
    del pixels

    return card.subsurface((0, 0, w, half)).copy(), card.subsurface((0, half, w, h - half)).copy()


# A copy of a picture with its colours scaled by k (less than 1 to darken it)
def shaded(image, k):
    image = image.copy()
    level = max(0, min(255, round(255 * k)))
    image.fill((level, level, level), special_flags=pygame.BLEND_RGB_MULT)
    return image


# One set of cards: the text it shows, and its fall from one to the next
class Flap:

    def __init__(self, rect, font):
        self.rect = pygame.Rect(rect)
        self.font = font
        self.halves = {}
        self.text = None
        self.old = None
        self.start = None       # when the card began to fall (or will), or None

    def halvesFor(self, text):
        if text not in self.halves:
            if len(self.halves) > 40:
                self.halves = {}
            self.halves[text] = cardHalves(text, self.rect.width, self.rect.height, self.font)
        return self.halves[text]

    # Change to the text, at once or with the card falling, `delay` seconds after `clock`
    def show(self, text, clock, animate, delay=0.0):
        if text == self.text:
            return
        if animate and self.text is not None:
            self.old = self.text
            self.start = clock + delay
        else:
            self.old, self.start = None, None
        self.text = text

    def draw(self, surface, clock):
        x, y, w, h = self.rect
        half = h // 2
        hinge = y + half
        newTop, newBottom = self.halvesFor(self.text)

        progress = None if self.start is None else (clock - self.start) / FLIP_SECONDS
        if progress is not None and progress >= 1:
            self.start, self.old, progress = None, None, None

        if progress is None or progress < 0:
            # still: the old card, until it starts to fall
            top, bottom = self.halvesFor(self.old) if progress is not None else (newTop, newBottom)
            surface.blit(top, (x, y))
            surface.blit(bottom, (x, hinge))
        else:
            oldTop, oldBottom = self.halvesFor(self.old)
            angle = math.pi * progress ** 1.7           # falling faster as it goes
            surface.blit(newTop, (x, y))
            surface.blit(shaded(oldBottom, 1 - 0.35 * math.sin(angle / 2)), (x, hinge))
            squash = abs(math.cos(angle))
            height = max(1, round(half * squash))
            width = round(w * (1 + 0.05 * math.sin(angle)))     # a little wider as it comes towards you
            if angle < math.pi / 2:
                flap = pygame.transform.smoothscale(oldTop, (width, height))
                flap = shaded(flap, 1 - 0.3 * math.sin(angle))
                surface.blit(flap, (x + (w - width) // 2, hinge - height))
            else:
                flap = pygame.transform.smoothscale(newBottom, (width, height))
                flap = shaded(flap, 0.7 + 0.3 * squash)
                surface.blit(flap, (x + (w - width) // 2, hinge))

        # the gap between the halves, and the pins the cards turn on
        pygame.draw.line(surface, (6, 6, 7), (x, hinge), (x + w - 1, hinge), 3)
        pinH = max(6, h // 18)
        for px in (x - 7, x + w - 1):
            pygame.draw.rect(surface, (120, 118, 112), (px, hinge - pinH // 2, 8, pinH), border_radius=2)


##==================================================================
## THE BACKGROUND
##==================================================================

# Big circles of orange, mustard and brown on brown paper
def wallpaper(xx, yy):
    tile = 200
    lx = xx % tile - tile / 2
    ly = (yy + (np.floor(xx / tile) % 2) * tile / 2) % tile - tile / 2
    r = np.hypot(lx, ly)
    colours = np.array([[196, 98, 36], [212, 160, 62], [116, 64, 32], [196, 98, 36], [72, 42, 26]], np.float32)
    band = np.clip(np.floor(r / 22), 0, 4).astype(int)
    band = np.where(r > 92, 4, band)
    rgb = colours[band]
    edge = np.abs((r % 22) - 11)
    rgb *= (0.92 + 0.08 * smoothstep(9, 11, edge))[..., None]
    return rgb


def drawBackground():
    w, h = scr.SCREEN_WIDTH, scr.SCREEN_HEIGHT
    xx, yy = screenGrid(w, h)
    rng = np.random.default_rng(53)

    rgb = wallpaper(xx, yy) * 0.62 * (1 + 0.04 * waves(xx, yy, 6, 120, rng) + rng.normal(0, 0.02, (h, w)))[..., None]
    cx = w / 2
    caseW = RECESS_W / 2 + CASE_EDGE
    caseD = roundedBox(xx, yy, cx, (TOP + CASE_BOTTOM) / 2, caseW, (CASE_BOTTOM - TOP) / 2, 90)

    # the case's shadow on the wall
    shadowD = roundedBox(xx - 36, yy - 30, cx, (TOP + CASE_BOTTOM) / 2, caseW, (CASE_BOTTOM - TOP) / 2, 90)
    rgb *= (1 - 0.6 * (1 - smoothstep(-40, 70, shadowD)))[..., None]

    # the sideboard: teak, its front edge catching the light
    board = yy >= CASE_BOTTOM
    grain = 0.82 + 0.1 * np.sin(xx * 0.02 + 7 * waves(xx, yy * 6, 5, 200, rng)) + 0.05 * waves(xx * 0.2, yy * 5, 6, 40, rng)
    boardRgb = np.array(TEAK, np.float32) * grain[..., None]
    boardRgb *= (1 - 0.55 * (1 - smoothstep(-30, 40, np.abs(xx - cx) - caseW - 10)) * (yy < CASE_BOTTOM + 40))[..., None]
    boardRgb += (50 * np.exp(-((yy - CASE_BOTTOM - 3) / 2) ** 2))[..., None]
    rgb = np.where(board[..., None], boardRgb, rgb)

    # the glossy plastic case, rounded all round its edge
    inside = np.clip(0.5 - caseD, 0, 1)
    nx, ny, nz = bevel(-caseD, 46)
    diffuse, specular = lighting(nx, ny, nz, 70)
    caseRgb = np.array(CASE, np.float32) * (0.5 + 0.55 * diffuse)[..., None] + (190 * specular)[..., None]
    rgb = rgb * (1 - inside[..., None]) + caseRgb * inside[..., None]

    # the black window the cards are in, set into the case, its top edge in shadow
    rd = roundedBox(xx, yy, cx, RECESS_TOP + RECESS_H / 2, RECESS_W / 2, RECESS_H / 2, 40)
    inRecess = np.clip(0.5 - rd, 0, 1)
    lip = np.exp(-(np.maximum(rd, 0) / 3) ** 2) * (rd > 0) * (rd < 12)
    rgb *= (1 - 0.35 * lip)[..., None]
    recessRgb = np.array(RECESS, np.float32) * (1 + 0.6 * smoothstep(RECESS_TOP, RECESS_TOP + RECESS_H, yy))[..., None]
    rgb = rgb * (1 - inRecess[..., None]) + recessRgb * inRecess[..., None]

    picture = toSurface(vignette(rgb, xx, yy, 0.4))

    # the edges of the cards stacked below each set
    for rect in flapRects():
        x, y, w, h = rect
        for i in range(1, 4):
            shade = 52 - 10 * i
            pygame.draw.line(picture, (shade, shade, shade + 2), (x + 4 * i, y + h + 3 * i), (x + w - 4 * i, y + h + 3 * i), 2)
    return picture


# The smoked plastic over the window: a faint light across it
def drawCover():
    yy, xx = np.mgrid[0:RECESS_H, 0:RECESS_W].astype(np.float32)
    d = roundedBox(xx, yy, RECESS_W / 2, RECESS_H / 2, RECESS_W / 2, RECESS_H / 2, 40)
    streak = np.exp(-((xx * 0.55 + yy - 0.42 * RECESS_W) / 90) ** 2) + 0.5 * np.exp(-((xx * 0.55 + yy - 0.62 * RECESS_W) / 25) ** 2)
    alpha = (16 + 22 * streak) * np.clip(0.5 - d, 0, 1)
    return toSurface(np.full((RECESS_H, RECESS_W, 3), 255, np.float32), alpha)


# Where the cards are: the hours, the minutes, then the day, the date and the month
def flapRects():
    left = RECESS_LEFT + MARGIN
    top = RECESS_TOP + MARGIN
    rects = [(left, top, BIG_W, BIG_H), (left + BIG_W + BIG_GAP, top, BIG_W, BIG_H)]
    x = (scr.SCREEN_WIDTH - (sum(SMALL_WIDTHS) + SMALL_GAP * (len(SMALL_WIDTHS) - 1))) // 2
    for width in SMALL_WIDTHS:
        rects.append((x, top + BIG_H + ROW_GAP, width, SMALL_H))
        x += width + SMALL_GAP
    return rects


##==================================================================
## THE SOUND
##==================================================================

# A card landing: a snap of plastic, and a knock in the case
def clack(seed, volume):
    rng = np.random.default_rng(seed)
    t = synth.times(0.15)
    click = synth.noise(0.15, rng)
    click = click - synth.smooth(click, 5)
    sound = 0.9 * click * np.exp(-t / 0.003)
    for f, decay, loudness in ((rng.uniform(1300, 1500), 0.012, 0.45), (rng.uniform(2500, 2900), 0.006, 0.3),
                               (rng.uniform(220, 260), 0.025, 0.7), (rng.uniform(520, 600), 0.015, 0.35)):
        sound += loudness * np.sin(2 * np.pi * f * t) * np.exp(-t / decay)
    sound *= np.minimum(1.0, t / 0.0004)
    return makeSound(sound, volume)


##==================================================================
## THE FACE
##==================================================================

# Each set of cards starts to fall this long after the minute begins
DELAYS = [0.18, 0.0, 0.36, 0.48, 0.60]


class FlipFace(Face):

    name = "FLIP"
    statusColour = TEXT_COLOUR

    def build(self, chimeVolume, tickVolume):
        self.background = drawBackground()
        self.cover = drawCover()
        big, small = flipFont(480), flipFont(160)
        self.flaps = [Flap(rect, big if i < 2 else small) for i, rect in enumerate(flapRects())]
        self.clacks = [clack(seed, tickVolume * 1.4) for seed in (61, 62, 63)]
        self.animate = False

    def sounds(self):
        return self.clacks

    def tickSounds(self):
        return self.clacks

    def enter(self):
        self.animate = False            # on coming back, show the time at once

    @staticmethod
    def texts(now):
        hour = now.hour if HOURS_24 else (now.hour % 12 or 12)
        return [f"{hour:02d}" if HOURS_24 else str(hour), f"{now.minute:02d}",
                now.strftime("%a").upper(), str(now.day), now.strftime("%b").upper()]

    # A clack as each card lands: the minutes, and the hours and the date if they change too
    def soundsAt(self, now):
        if now.second != 0:
            return []
        changing = [1]
        if now.minute == 0:
            changing.append(0)
            if now.hour == 0:
                changing += [2, 3, 4]
        return [(DELAYS[i] + FLIP_SECONDS, self.clacks[n % len(self.clacks)], "tick") for n, i in enumerate(changing)]

    def update(self, now):
        self.clock = now.timestamp()
        for flap, text, delay in zip(self.flaps, self.texts(now), DELAYS):
            flap.show(text, self.clock, self.animate, delay)
        self.animate = True

    def draw(self, surface):
        surface.blit(self.background, (0, 0))
        for flap in self.flaps:
            flap.draw(surface, self.clock)
        surface.blit(self.cover, (RECESS_LEFT, RECESS_TOP))
