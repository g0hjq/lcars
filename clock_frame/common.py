"""
common.py

What the clock's faces share: the Face they are each based on, a base for the analogue
ones (AnalogueFace), and helpers for drawing with numpy and for making their sounds.

A face draws the whole screen, and says which sounds to play when. To add one, make a
class based on Face (or AnalogueFace) in a file of its own, add it to FACE_CLASSES in
clock.py, and add its name to CLOCK_FACES in settings.py.

    class MyFace(Face):
        name = "MINE"                       # shown when the OK button changes to it

        def build(self, chimeVolume, tickVolume):
            ...                             # once, the first time it is shown: drawing and sounds

        def update(self, now):
            ...                             # every frame while it is shown

        def draw(self, surface):
            ...                             # the whole screen

        def chime(self, hour, minute):
            return [(0, self.bong)]         # the sounds due at this quarter, as (seconds later, Sound)

        beats = 1                           # ticks a second (only heard while it is shown)...

        def beatSound(self, now, beat):
            return self.tock                # ...and the sound of each one
"""

import math
import pygame
import numpy as np
import synth

SAMPLE_RATE = synth.SAMPLE_RATE

SS = 3                          # fine detail is drawn this many times bigger, then shrunk, for smooth edges
LIGHT = np.array([-0.45, -0.6, 0.66])    # where the light comes from: up and to the left (x right, y down, z out)
LIGHT = LIGHT / np.linalg.norm(LIGHT)

CHIME = "chime"                 # what kind a sound is: chimes can be heard behind the other screens...
TICK = "tick"                   # ...but ticks only while the clock is shown

SANS_FONTS = "dejavusans,freesans,arial,sans"
SERIF_FONTS = "freeserif,timesnewroman,dejavuserif,serif"


##==================================================================
## THE FACES
##==================================================================

class Face:

    name = "FACE"
    statusColour = (222, 186, 112)  # the colour and the fonts of the notice in the corner at night
    statusFonts = SANS_FONTS
    statusItalic = False

    def build(self, chimeVolume, tickVolume):
        pass

    # All its Sounds...
    def sounds(self):
        return []

    # ...and which of them are ticks (or clacks, or clunks): the SOUND button sets how loud
    # these are, and the rest (the chimes) are always as loud as they were made
    def tickSounds(self):
        return []

    # The sounds due when the clock reaches hour:minute (a whole quarter), as (seconds later,
    # Sound): the quarter's chime, say, and the strokes of the hour after it
    def chime(self, hour, minute):
        return []

    # How many times a second it ticks (0: never), and the sound of each tick: beat is which
    # of them it is in the second `now` (0 for the one as the second begins), and None is
    # silence. The ticks are played on time by a thread of their own (see ClockScreen), so
    # that they are evenly spaced, as the frames the screen is drawn in are not.
    beats = 0

    def beatSound(self, now, beat):
        return None

    # The other sounds to start as this second begins, as (seconds later, Sound, CHIME or
    # TICK). Unless a face changes it, it chimes at each quarter.
    def soundsAt(self, now):
        if now.second == 0 and now.minute % 15 == 0:
            return [(later, sound, CHIME) for later, sound in self.chime(now.hour, now.minute)]
        return []

    # When it is about to be shown, having been hidden (behind another screen, or another face)
    def enter(self):
        pass

    def update(self, now):
        pass

    def draw(self, surface):
        raise NotImplementedError


# A clock with hands: the background, a dial (with its case) 2 * radius across with its middle
# at centre, three Hands, a nut over them and perhaps a glass. A face based on it fills them
# in in build. The dial and the hour and minute hands are put together only when they move;
# the seconds hand is put on a copy of that, each time it moves.
class AnalogueFace(Face):

    centre = (960, 540)
    radius = 500

    def build(self, chimeVolume, tickVolume):
        self.background = None      # the whole screen, with the clock's shadow on it
        self.dial = None            # the dial and case, 2 * radius across, with see-through corners
        self.hands = None           # hour, minute and second Hands
        self.nut = None             # a small picture to go over the middle, or None
        self.glass = None           # (picture, where) of the reflection over the dial, or None

    # The dial to show at this time (a face can show a different one by day, or by night)
    def dialFor(self, now):
        return self.dial

    # Where the hands point: hour, minute and second, in degrees clockwise from 12
    def angles(self, now):
        seconds = now.second + now.microsecond / 1e6
        minutes = now.minute + seconds / 60
        hours = now.hour % 12 + minutes / 60
        return hours * 30, minutes * 6, seconds * 6

    def enter(self):
        self.slowKey = None
        self.fastKey = None

    def update(self, now):
        hourAngle, minuteAngle, secondAngle = self.angles(now)
        dial = self.dialFor(now)
        middle = (self.radius, self.radius)

        slowKey = (id(dial), round(hourAngle, 1), round(minuteAngle, 1))
        if slowKey != self.slowKey:
            self.slowKey = slowKey
            self.fastKey = None
            area = pygame.Rect(0, 0, 2 * self.radius, 2 * self.radius)
            area.center = self.centre
            self.under = self.background.subsurface(area).copy()
            self.under.blit(dial, (0, 0))
            hour, minute, _ = self.hands
            hour.draw(self.under, hourAngle, middle)
            minute.draw(self.under, minuteAngle, middle)

        fastKey = (slowKey, round(secondAngle, 1))
        if fastKey != self.fastKey:
            self.fastKey = fastKey
            self.image = self.under.copy()
            self.hands[2].draw(self.image, secondAngle, middle)
            if self.nut:
                self.image.blit(self.nut, self.nut.get_rect(center=middle))
            if self.glass:
                self.image.blit(*self.glass)

    def draw(self, surface):
        surface.blit(self.background, (0, 0))
        surface.blit(self.image, self.image.get_rect(center=self.centre))


##==================================================================
## DRAWING HELPERS
##==================================================================

# How far each pixel of a size x size square is from its middle, and the direction to it
def polarGrid(size):
    c = (size - 1) / 2
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    dx = xx - c
    dy = yy - c
    r = np.sqrt(dx * dx + dy * dy)
    with np.errstate(invalid="ignore", divide="ignore"):
        ux = np.where(r > 0, dx / r, 0)
        uy = np.where(r > 0, dy / r, 0)
    return r, ux, uy, dx, dy


# The x and y of each pixel of the screen (or of a w x h area)
def screenGrid(w, h):
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    return xx, yy


def smoothstep(edge0, edge1, x):
    t = np.clip((x - edge0) / (edge1 - edge0), 0, 1)
    return t * t * (3 - 2 * t)


# Smooth random hills, by adding together a few waves going in random directions
def waves(xx, yy, count, scale, rng):
    total = np.zeros_like(xx)
    for _ in range(count):
        angle = rng.uniform(0, math.pi)
        k = rng.uniform(0.5, 1.5) / scale
        total += np.sin((xx * math.cos(angle) + yy * math.sin(angle)) * k + rng.uniform(0, 6.3))
    return total / math.sqrt(count)


# A surface from a (height, width, 3) array of colours, and an optional (height, width) alpha
def toSurface(rgb, alpha=None):
    rgb = np.clip(rgb, 0, 255).astype(np.uint8)
    if alpha is None:
        return pygame.surfarray.make_surface(rgb.transpose(1, 0, 2))

    alpha = np.clip(alpha, 0, 255).astype(np.uint8)
    rgba = np.dstack((rgb, alpha))
    return pygame.image.frombuffer(rgba.tobytes(), (rgb.shape[1], rgb.shape[0]), "RGBA").convert_alpha()


# The light on a surface facing (nx, ny, nz): how much it is lit, and its shine
def lighting(nx, ny, nz, shininess=60):
    diffuse = np.clip(nx * LIGHT[0] + ny * LIGHT[1] + nz * LIGHT[2], 0, 1)
    half = LIGHT + np.array([0, 0, 1.0])
    half = half / np.linalg.norm(half)
    specular = np.clip(nx * half[0] + ny * half[1] + nz * half[2], 0, 1) ** shininess
    return diffuse, specular


# The light on a raised round shape, whose height at each radius is given by profile
def shadeProfile(r, ux, uy, profileR, profileH, shininess=60):
    slope = np.interp(r, profileR, np.gradient(profileH, profileR))
    nx, ny, nz = -slope * ux, -slope * uy, np.ones_like(r)
    length = np.sqrt(nx * nx + ny * ny + nz * nz)
    return lighting(nx / length, ny / length, nz / length, shininess)


# Which way a flat shape with rounded edges faces, given how far each pixel is inside its edge
# (minus outside): flat in the middle, curving down over the last `width` pixels
def bevel(inside, width):
    t = np.clip(inside / width, 0, 1)
    height = np.sqrt(1 - (1 - t) ** 2) * width
    gy, gx = np.gradient(height)
    nz = np.ones_like(height)
    length = np.sqrt(gx * gx + gy * gy + 1)
    return -gx / length, -gy / length, nz / length


# Polished chrome facing (nx, ny, nz): it shows the room reflected in it, a bright window
# above, a dark band at the horizon and a duller floor below
def chrome(nx, ny, nz):
    ry = 2 * nz * ny                # the reflected ray's up and down (minus is up)
    rx = 2 * nz * nx
    sky = 0.55 + 0.45 * smoothstep(0.05, -0.6, ry)
    horizon = np.exp(-((ry - 0.12) / 0.12) ** 2)
    level = sky * (1 - 0.75 * horizon) - 0.25 * smoothstep(0.2, 0.9, ry) + 0.12 * np.sin(rx * 3)
    return np.clip(level, 0.05, 1.1)


# Distance from a rounded rectangle's edge (minus inside), for numpy arrays of x and y
def roundedBox(xx, yy, cx, cy, halfW, halfH, corner):
    qx = np.abs(xx - cx) - (halfW - corner)
    qy = np.abs(yy - cy) - (halfH - corner)
    outside = np.sqrt(np.maximum(qx, 0) ** 2 + np.maximum(qy, 0) ** 2)
    return outside + np.minimum(np.maximum(qx, qy), 0) - corner


# Darker towards the corners of the screen
def vignette(rgb, xx, yy, strength=0.45):
    h, w = xx.shape
    cx, cy = w / 2, h / 2
    corner = np.sqrt(((xx - cx) / cx) ** 2 + ((yy - cy) / cy) ** 2)
    return rgb * (1 - strength * smoothstep(0.6, 1.5, corner))[..., None]


# A soft shadow under a shape, given how far each pixel is outside its edge, falling down and
# to the right of where the shape is
def softShadow(rgb, outside, depth=0.7, spread=30):
    return rgb * (1 - depth * (1 - smoothstep(-spread, spread * 1.6, outside)))[..., None]


# A small polished dome, such as the nut in the middle that holds the hands on
def dome(radius, colour):
    size = int(radius * 2 + 4)
    r, ux, uy, _, _ = polarGrid(size)
    rs = np.linspace(0, radius + 2, 200)
    hs = np.sqrt(np.clip(radius * radius - rs * rs, 0, None)) * 0.8
    diffuse, specular = shadeProfile(r, ux, uy, rs, hs)
    colour = np.array(colour, dtype=np.float32)
    rgb = colour * (0.3 + 0.85 * diffuse)[..., None] + 255 * 0.9 * specular[..., None]
    alpha = np.clip(radius + 0.5 - r, 0, 1) * 255
    return toSurface(rgb, alpha)


# The glass over a dial: a soft reflection of the window, up and to the left. Returns the
# picture and where to put it on a picture of the clock 2 * radius across.
def drawGlass(radius, dialRadius, strength=1.0):
    size = 2 * radius
    r, _, _, dx, dy = polarGrid(size)
    hx, hy = -0.32 * radius, -0.42 * radius
    glow = np.exp(-(((dx - hx) / (0.42 * radius)) ** 2 + ((dy - hy) / (0.28 * radius)) ** 2))
    streak = np.exp(-((dx + dy + 0.95 * radius) / (0.05 * radius)) ** 2) * (1 - smoothstep(0.55 * radius, dialRadius, r))
    alpha = strength * (34 * glow + 22 * streak) * np.clip(dialRadius - r, 0, 1)
    rgb = np.full((size, size, 3), 255, dtype=np.float32)
    glass = toSurface(rgb, alpha)
    area = glass.get_bounding_rect()        # only the part that can be seen, as it is put on each frame
    return glass.subsurface(area).copy(), area.topleft


# Text, with its middle at (x, y), turned by angle degrees clockwise
def blitText(surface, font, text, colour, x, y, angle=0):
    image = font.render(text, True, colour)
    if angle:
        image = pygame.transform.rotozoom(image, -angle, 1)
    surface.blit(image, image.get_rect(center=(round(x), round(y))))


def sysFont(names, size, bold=False, italic=False):
    return pygame.font.SysFont(names, size, bold=bold, italic=italic)


##==================================================================
## HANDS
##==================================================================

# A hand, pointing up, with the point it turns about (its pivot) in its picture
class Hand:

    def __init__(self, surface, pivot, shadowOffset):
        self.surface = surface
        self.pivot = pygame.math.Vector2(pivot)
        self.shadow, self.shadowPivot = makeShadow(surface, self.pivot)
        self.shadowOffset = pygame.math.Vector2(shadowOffset)

    # Its picture turned to the angle (degrees clockwise from 12), and where to put it so
    # that its pivot is at centre
    @staticmethod
    def turned(surface, pivot, angle, centre):
        image = pygame.transform.rotozoom(surface, -angle, 1)
        middle = pygame.math.Vector2(surface.get_size()) / 2
        offset = (middle - pivot).rotate(angle)
        return image, image.get_rect(center=(round(centre[0] + offset.x), round(centre[1] + offset.y)))

    def draw(self, surface, angle, centre):
        shadowCentre = pygame.math.Vector2(centre) + self.shadowOffset
        surface.blit(*self.turned(self.shadow, self.shadowPivot, angle, shadowCentre))
        surface.blit(*self.turned(self.surface, self.pivot, angle, centre))


# A soft dark copy of the hand, for its shadow on the dial
def makeShadow(surface, pivot):
    pad = 10
    w, h = surface.get_size()
    shadow = pygame.Surface((w + 2 * pad, h + 2 * pad), pygame.SRCALPHA)
    shadow.fill((0, 0, 0, 0))
    shadow.blit(surface, (pad, pad))
    shadow.fill((0, 0, 0, 255), special_flags=pygame.BLEND_RGBA_MIN)
    shadow.fill((255, 255, 255, 120), special_flags=pygame.BLEND_RGBA_MULT)
    small = pygame.transform.smoothscale(shadow, (max(1, (w + 2 * pad) // 4), max(1, (h + 2 * pad) // 4)))
    shadow = pygame.transform.smoothscale(small, (w + 2 * pad, h + 2 * pad))
    return shadow, pivot + pygame.math.Vector2(pad, pad)


# Draws a hand, given the shapes it is made of, measured in pixels: x across (minus is the
# left), and y along it from the pivot (minus is the tail). The left side is drawn in litColour,
# as though the light catches that slope of it.
#   ("poly", [(x, y), ...])     a polygon
#   ("disc", y, radius)         a disc on the middle line
#   ("hole", y, radius)         a hole through what is drawn before it
def makeHand(length, tail, halfWidth, shapes, shadowOffset, colour, litColour=None):
    w = int(2 * halfWidth + 6)
    h = int(length + tail + 6)
    pivot = (w / 2, length + 3)

    def p(x, y):
        return ((pivot[0] + x) * SS, (pivot[1] - y) * SS)

    def render(colour):
        image = pygame.Surface((w * SS, h * SS), pygame.SRCALPHA)
        image.fill((*colour, 0))
        for kind, *data in shapes:
            if kind == "poly":
                pygame.draw.polygon(image, colour, [p(x, y) for x, y in data[0]])
            elif kind == "disc":
                y, radius = data
                pygame.draw.circle(image, colour, p(0, y), radius * SS)
            elif kind == "hole":
                y, radius = data
                pygame.draw.circle(image, (*colour, 0), p(0, y), radius * SS)
        return image

    image = render(colour)
    if litColour:
        lit = render(litColour)
        image.blit(lit, (0, 0), pygame.Rect(0, 0, round(pivot[0] * SS), h * SS))
    image = pygame.transform.smoothscale(image, (w, h))
    return Hand(image, pivot, shadowOffset)


# A tapering bar from y0 to y1, w0 wide at y0 and w1 wide at y1 (w1 = 0 for a point)
def taper(y0, y1, w0, w1):
    return ("poly", [(-w0 / 2, y0), (-w1 / 2, y1), (w1 / 2, y1), (w0 / 2, y0)] if w1 else
                    [(-w0 / 2, y0), (0, y1), (w0 / 2, y0)])


# How far a hand that jumps has got to its next mark, 0 to 1, over `seconds`, overshooting a
# little and settling back, the way a real one does
def settle(fraction, seconds=0.3):
    t = min(1.0, fraction / seconds) * 3.3
    return 1 - math.exp(-2.4 * t) * math.cos(3.1 * t)


##==================================================================
## SOUNDS
##==================================================================

# The partials of a bell: (times the note's frequency, loudness, seconds to die away to a third)
BELL_PARTIALS = [
    (0.5,   0.30, 3.2),         # hum
    (1.0,   1.00, 2.4),         # prime: the note itself
    (1.19,  0.42, 1.6),         # tierce, the minor third that makes it sound like a bell
    (1.50,  0.25, 1.3),         # quint
    (2.0,   0.55, 1.1),         # nominal
    (2.52,  0.22, 0.7),
    (2.66,  0.18, 0.6),
    (3.01,  0.14, 0.45),
    (4.17,  0.08, 0.3),
]

# A struck metal rod, as the chimes of a mantel clock are: its overtones are far from the note
ROD_PARTIALS = [
    (1.0,   1.00, 1.6),
    (2.756, 0.45, 0.7),
    (5.404, 0.18, 0.3),
    (8.933, 0.06, 0.15),
]


# One stroke of a bell (or a rod), as a numpy array of floats, peaking at about 1
def bellStroke(frequency, ringSeconds, decayScale=1.0, partials=BELL_PARTIALS, hammer=0.06):
    t = synth.times(ringSeconds)
    sound = np.zeros_like(t)
    rng = np.random.default_rng(int(frequency))

    for ratio, loudness, decay in partials:
        f = frequency * ratio
        if f > SAMPLE_RATE / 2.5:
            continue
        envelope = loudness * np.exp(-t / (decay * decayScale))
        phase = rng.uniform(0, 2 * math.pi)

        # each partial is two tones very slightly apart, which beat slowly, as a real bell's do
        sound += envelope * np.sin(2 * math.pi * f * t + phase)
        sound += 0.45 * envelope * np.sin(2 * math.pi * f * 1.0013 * t + phase)

    # the tap of the hammer
    sound += hammer * rng.uniform(-1, 1, len(t)) * np.exp(-t / 0.003)

    attack = np.minimum(1.0, t / 0.002)             # no click at the start
    release = np.minimum(1.0, (t[-1] - t) / 0.2)    # nor at the end
    sound *= attack * release
    return sound / np.max(np.abs(sound))


# The tick or the tock of an old pendulum clock: the pallet knocking against the escape
# wheel, and the tooth dropping a moment later, each ringing the steel a little and making
# the hollow wooden case knock. pitch scales the steel's ring (and the case's knock a little),
# and drop is the seconds between the two knocks.
TICK_STEEL = [(950, 0.3, 0.005), (1600, 0.12, 0.003)]   # (Hz, loudness, seconds to die away)
TICK_CASE = [(150, 1.0, 0.040), (310, 0.7, 0.028), (520, 0.45, 0.018), (820, 0.25, 0.010)]

def tickStroke(pitch, drop, dropLoudness, case=1.0):
    t = synth.times(0.15)
    rng = np.random.default_rng(int(pitch * 1000))
    sound = np.zeros_like(t)

    for at, loudness in ((0.0, 1.0), (drop, dropLoudness)):
        tt = t - at
        on = tt >= 0
        tt = np.where(on, tt, 0)

        # a dull knock: noise with the hiss taken off
        knock = np.convolve(rng.uniform(-1, 1, len(t)), np.ones(20) / 20, "same") * np.exp(-tt / 0.002)
        part = 0.8 * knock
        for f, amp, decay in TICK_STEEL:
            part += amp * np.sin(2 * math.pi * f * pitch * tt + rng.uniform(0, 6.3)) * np.exp(-tt / decay)
        for f, amp, decay in TICK_CASE:
            part += case * amp * np.sin(2 * math.pi * f * (0.5 + 0.5 * pitch) * tt + rng.uniform(0, 6.3)) * np.exp(-tt / decay)
        sound += loudness * part * on * np.minimum(1.0, tt / 0.0003)

    sound *= np.minimum(1.0, (t[-1] - t) / 0.02)
    return sound / np.max(np.abs(sound))


# Notes, one after another, each a numpy array: (seconds from the start, samples, loudness,
# pan from 0 left to 1 right), mixed into a stereo array with a second to spare at the end
def mixNotes(notes):
    length = max(at + len(samples) / SAMPLE_RATE for at, samples, _, _ in notes) + 1.0
    mix = np.zeros((int(length * SAMPLE_RATE), 2))
    for at, samples, loudness, pan in notes:
        synth.mixIn(mix[:, 0], samples * loudness * (1 - pan) * 2, at)
        synth.mixIn(mix[:, 1], samples * loudness * pan * 2, at)
    return mix


# A pygame Sound from a mono or stereo numpy array of floats, in a little room: a few faint,
# slightly late copies, different on each side. None if there is no sound.
def makeSound(samples, volume):
    if samples.ndim == 1:
        samples = np.column_stack((samples, samples))

    room = samples.copy()
    for delay, gain, side in ((0.023, 0.22, 0), (0.031, 0.20, 1), (0.047, 0.14, 0), (0.059, 0.12, 1)):
        n = int(delay * SAMPLE_RATE)
        room[n:, side] += gain * samples[:-n, side]

    return synth.makeSound(room, volume)
