"""
railway.py

A station clock, hanging from a rod in front of a painted brick wall: a plain white dial with
black bars for the hours and minutes, black hands, and a red seconds hand with a disc near its
end. As on the real thing, the seconds hand sweeps round in a little less than a minute
(SWEEP_SECONDS), waits at the top, and lets the minute hand jump on when the minute begins.

Each minute the hand moves with a soft clunk, and on the hour a chime rings as though for a
station announcement.
"""

import math
import pygame
import numpy as np
import screens as scr
from .common import (AnalogueFace, SS, LIGHT, polarGrid, screenGrid, smoothstep, waves, toSurface,
                     shadeProfile, dome, drawGlass, makeHand, taper, settle, mixNotes, makeSound)
import synth

##==================================================================
## SETTINGS (they are in settings.py, next to lcars.py)
##==================================================================

from settings import (
    RAILWAY_SWEEP_SECONDS as SWEEP_SECONDS,
    RAILWAY_MINUTE_SETTLE as MINUTE_SETTLE,
    RAILWAY_HOURLY_CHIME as HOURLY_CHIME,
    RAILWAY_CLOCK_RADIUS as CLOCK_RADIUS,
    RAILWAY_CLOCK_CENTRE as CLOCK_CENTRE,
    RAILWAY_DADO_Y as DADO_Y,
    RAILWAY_DIAL as DIAL,
    RAILWAY_INK as INK,
    RAILWAY_INK_LIGHT as INK_LIGHT,
    RAILWAY_RED as RED,
    RAILWAY_RED_LIGHT as RED_LIGHT,
    RAILWAY_CASE as CASE,
    RAILWAY_WALL_UPPER as WALL_UPPER,
    RAILWAY_WALL_LOWER as WALL_LOWER,
    RAILWAY_DADO as DADO,
    RAILWAY_TEXT_COLOUR as TEXT_COLOUR,
)

R = CLOCK_RADIUS
DIAL_RADIUS = 0.885 * R


##==================================================================
## THE SOUNDS
##==================================================================

# One note of a vibraphone: a pure tone, a quieter one two octaves up, and a slow wobble
def vibraphone(frequency, seconds):
    t = synth.times(seconds)
    sound = np.zeros_like(t)
    for ratio, loudness, decay in ((1.0, 1.0, 1.8), (4.0, 0.25, 0.4), (10.0, 0.05, 0.1)):
        sound += loudness * np.sin(2 * math.pi * frequency * ratio * t) * np.exp(-t / decay)
    sound *= 1 + 0.22 * np.sin(2 * math.pi * 5.5 * t)
    sound *= np.minimum(1.0, t / 0.004) * np.minimum(1.0, (t[-1] - t) / 0.3)
    return sound


# The chime before an announcement: four notes going up
def stationChime(volume):
    notes = [(392.00, 0.40), (523.25, 0.44), (659.26, 0.48), (783.99, 0.62)]
    return makeSound(mixNotes([(i * 0.5, vibraphone(f, 4.0), loudness, 0.4 + 0.07 * i)
                               for i, (f, loudness) in enumerate(notes)]), volume)


# The minute hand jumping: the clunk of the movement, and the hand ringing a little
def clunk(volume):
    t = synth.times(0.25)
    rng = np.random.default_rng(17)
    sound = 0.6 * synth.smooth(synth.noise(0.25, rng), 12) * np.exp(-t / 0.004)
    for f, loudness, decay in ((95, 1.0, 0.05), (210, 0.6, 0.03), (480, 0.25, 0.015), (1850, 0.06, 0.04)):
        sound += loudness * np.sin(2 * math.pi * f * t) * np.exp(-t / decay)
    sound *= np.minimum(1.0, t / 0.0005)
    return makeSound(sound, volume)


##==================================================================
## DRAWING
##==================================================================

# Bricks painted cream above the dado line and green below, the clock's rod coming down from
# above, and the shadows of both
def drawBackground():
    w, h = scr.SCREEN_WIDTH, scr.SCREEN_HEIGHT
    xx, yy = screenGrid(w, h)
    rng = np.random.default_rng(23)

    # the bricks, each row half a brick along from the last, with mortar between them
    bw, bh, mortar = 150, 52, 7
    row = np.floor(yy / bh)
    bx = (xx + (row % 2) * bw / 2) % bw
    by = yy % bh
    groove = np.minimum(np.minimum(bx, bw - bx), np.minimum(by, bh - by))
    inBrick = smoothstep(mortar / 2 - 1.5, mortar / 2 + 1.5, groove)
    brickId = (row * 37 + np.floor((xx + (row % 2) * bw / 2) / bw) * 11) % 17
    brickTone = 1 + 0.03 * (brickId / 8 - 1)
    # the light from above catches the top edge of each brick, and the bottom edge is in shadow
    edge = smoothstep(mortar / 2 + 4, mortar / 2, groove)
    topOrBottom = np.where(by < bh / 2, 0.05, -0.08)
    shade = (0.82 + 0.18 * inBrick) * brickTone * (1 + topOrBottom * edge * inBrick)
    shade += 0.025 * waves(xx, yy, 6, 60, rng) + rng.normal(0, 0.015, (h, w))

    paint = np.where((yy < DADO_Y)[..., None], np.array(WALL_UPPER, np.float32), np.array(WALL_LOWER, np.float32))
    dado = (np.abs(yy - DADO_Y) < 9)
    paint[dado] = DADO
    rgb = paint * shade[..., None]

    # light from up and to the left: the wall is a little darker down and to the right
    rgb *= (1.05 - 0.25 * smoothstep(0, w + h, xx + yy))[..., None]

    # the rod the clock hangs from
    cx, top = CLOCK_CENTRE[0], CLOCK_CENTRE[1] - R
    rodHalf = 17

    # the shadows of the clock and the rod, which hang out from the wall, so fall well away
    sx, sy = cx + 40, CLOCK_CENTRE[1] + 50
    distance = np.sqrt((xx - sx) ** 2 + (yy - sy) ** 2)
    shadow = 1 - smoothstep(R - 60, R + 70, distance)
    rodShadow = (1 - smoothstep(rodHalf - 10, rodHalf + 25, np.abs(xx - (cx + 40)))) * (yy < sy)
    rgb *= (1 - 0.45 * np.maximum(shadow, rodShadow))[..., None]

    # the rod itself: a round black iron bar, lit from the left
    across = np.clip((xx - cx) / rodHalf, -1, 1)
    onRod = np.clip(rodHalf + 0.5 - np.abs(xx - cx), 0, 1) * (yy < top + 30)
    nx = across
    nz = np.sqrt(np.clip(1 - across ** 2, 0, 1))
    lit = np.clip(nx * LIGHT[0] + nz * LIGHT[2], 0, 1)
    rodRgb = np.array(CASE, np.float32) * (0.35 + 0.8 * lit)[..., None] + 120 * (lit ** 30)[..., None]
    rgb = rgb * (1 - onRod[..., None]) + rodRgb * onRod[..., None]

    return toSurface(rgb)


# The dark metal case and the white dial, with its bars
def drawFace():
    size = 2 * R
    r, ux, uy, dx, dy = polarGrid(size)

    # the case: a thick rounded rim
    rs = np.linspace(0, R + 2, 2000)
    rimMid, rimHalf = (R + DIAL_RADIUS) / 2, (R - DIAL_RADIUS) / 2
    hs = np.sqrt(np.clip(1 - ((rs - rimMid) / rimHalf) ** 2, 0, None)) * rimHalf * 0.7
    diffuse, specular = shadeProfile(r, ux, uy, rs, hs, shininess=25)
    caseRgb = np.array(CASE, np.float32) * (0.3 + 0.9 * diffuse)[..., None] + 160 * specular[..., None]

    # the dial: white, a little shaded by the case on the side away from the light
    shift = 0.02 * R
    sr = np.sqrt((dx + LIGHT[0] * shift) ** 2 + (dy + LIGHT[1] * shift) ** 2)
    shadow = smoothstep(DIAL_RADIUS - 0.05 * R, DIAL_RADIUS + 0.01 * R, sr)
    dialRgb = np.array(DIAL, np.float32) * ((1 - 0.05 * r / R) * (1 - 0.35 * shadow))[..., None]

    inDial = np.clip(DIAL_RADIUS + 0.5 - r, 0, 1)[..., None]
    rgb = dialRgb * inDial + caseRgb * (1 - inDial)
    alpha = np.clip(R - 0.5 - r, 0, 1) * 255
    face = toSurface(rgb, alpha)
    face.blit(drawBars(), (0, 0))
    return face


# A bar for each minute, and longer, thicker ones for the hours
def drawBars():
    big = 2 * R * SS
    c = R * SS
    marks = pygame.Surface((big, big), pygame.SRCALPHA)
    marks.fill((*INK, 0))
    outer = 0.845 * R

    for minute in range(60):
        if minute % 5:
            inner, width = 0.785 * R, 0.0135 * R
        else:
            inner, width = 0.615 * R, 0.037 * R
        a = math.radians(minute * 6)
        along = (math.sin(a), -math.cos(a))
        side = (math.cos(a), math.sin(a))
        points = [(c + (rr * along[0] + s * width / 2 * side[0]) * SS, c + (rr * along[1] + s * width / 2 * side[1]) * SS)
                  for rr, s in ((inner, -1), (outer, -1), (outer, 1), (inner, 1))]
        pygame.draw.polygon(marks, INK, points)

    return pygame.transform.smoothscale(marks, (2 * R, 2 * R))


# Plain tapering bars, and the red seconds hand with its disc
def makeHands():
    hour = makeHand(0.62 * R, 0.24 * R, 0.04 * R, [
        taper(-0.24 * R, 0.62 * R, 0.075 * R, 0.062 * R),
    ], (8, 11), INK, INK_LIGHT)

    minute = makeHand(0.87 * R, 0.24 * R, 0.032 * R, [
        taper(-0.24 * R, 0.87 * R, 0.062 * R, 0.046 * R),
    ], (11, 15), INK, INK_LIGHT)

    second = makeHand(0.6 * R + 0.075 * R, 0.31 * R, 0.08 * R, [
        taper(-0.31 * R, 0.6 * R, 0.021 * R, 0.016 * R),
        ("disc", 0.6 * R, 0.075 * R),
        ("disc", 0, 0.03 * R),
    ], (14, 19), RED, RED_LIGHT)

    return hour, minute, second


##==================================================================
## THE FACE
##==================================================================

class RailwayFace(AnalogueFace):

    name = "RAILWAY"
    centre = CLOCK_CENTRE
    radius = R
    statusColour = TEXT_COLOUR

    def build(self, chimeVolume, tickVolume):
        self.background = drawBackground()
        self.dial = drawFace()
        self.hands = makeHands()
        self.nut = dome(0.018 * R, (150, 150, 150))
        self.glass = drawGlass(R, DIAL_RADIUS, strength=0.7)
        self.chimeSound = stationChime(chimeVolume)
        self.clunk = clunk(tickVolume)

    def sounds(self):
        return [self.chimeSound, self.clunk]

    def tickSounds(self):
        return [self.clunk]

    # The seconds hand sweeps round in SWEEP_SECONDS and waits; the minute hand (and the hour
    # hand with it) jumps on as the minute begins
    def angles(self, now):
        seconds = now.second + now.microsecond / 1e6
        minutes = now.minute - 1 + settle(seconds, MINUTE_SETTLE)
        hours = now.hour % 12 + minutes / 60
        return hours * 30, minutes * 6, min(1.0, seconds / SWEEP_SECONDS) * 360

    def chime(self, hour, minute):
        return [(0, self.chimeSound)] if minute == 0 and HOURLY_CHIME else []

    # The clunk of the minute hand jumping, as each minute begins
    beats = 1

    def beatSound(self, now, beat):
        return self.clunk if now.second == 0 else None
