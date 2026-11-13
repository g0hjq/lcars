"""
clock.py

A screen with a big old-fashioned clock on it: a brass case round an aged ivory dial with
Roman numerals, blued steel hands, and a ticking seconds hand. Through a window at the top
of the dial a painted moon shows the moon's phase, as on an old longcase clock, and three
little windows below the middle show the day, the date and the month.

It chimes the Westminster Quarters, like a mantel clock: one phrase at a quarter past, two
at half past, three at a quarter to, and all four on the hour, followed by a deeper bell
striking the hour. The bells are made from their tones when the program starts, so there
are no sound files. While it is shown it also ticks, gently.

The middle (OK) button, or Enter, goes round: chimes and ticking, chimes only, ticking
only, and silent. Holding it down (or Delete)
plays the last chime again, like the repeat on an old clock. Between QUIET_FROM and
QUIET_UNTIL it neither ticks nor chimes.

The case, the dial and the wooden background never change, so they are drawn once, when
the program starts. Each frame only the hands are put on top, and only when they have moved.

Uses numpy (on Raspberry Pi OS already; otherwise sudo apt install python3-numpy). The
text is in FreeSerif on the Pi (Times New Roman on Windows).
"""

import datetime
import math
import pygame
import numpy as np
import screens as scr

##==================================================================
## CONFIGURATION
##==================================================================

CHIME = True                    # False: a silent clock
CHIME_WHEN_HIDDEN = True        # True: chime even while another screen is shown (the tick is only heard on this one)
CHIME_VOLUME = 0.6              # 0 to 1
TICK_VOLUME = 0.12              # 0 to 1
STRIKE_HOURS = True             # after the hour's chime, strike the hour (once for one o'clock...)
QUIET_FROM = 0                  # no ticks or chimes from this hour (0 is midnight)...
QUIET_UNTIL = 9                 # ...until this one, so the 9 o'clock chime is the first of the day
MOTTO = "Tempus Fugit"          # written on the dial...
EVENING_MOTTO = "Beer O'Clock"  # ...or this, from EVENING_FROM until midnight
EVENING_FROM = 22

CLOCK_RADIUS = 500              # the outside of the brass case, in pixels
CLOCK_CENTRE = (960, 540)
STATUS_CORNER = (1890, 1050)    # the bottom right corner of the sound notices

FONT_NAMES = "freeserif,timesnewroman,dejavuserif,serif"

INK = (32, 27, 22)              # the numerals and the lines on the dial
BRASS = (196, 152, 74)
STEEL = (16, 20, 44)            # the blued steel of the hands...
STEEL_LIGHT = (48, 62, 118)     # ...and its lit side
TEXT_COLOUR = (222, 186, 112)
CARD = (243, 236, 220)          # the calendar wheels seen through their windows
SKY = (20, 36, 92)              # the moon disc's night sky
MOON = (232, 206, 140)          # its painted gold moons

SS = 3                          # fine detail is drawn this many times bigger, then shrunk, for smooth edges
LIGHT = np.array([-0.45, -0.6, 0.66])    # where the light comes from: up and to the left (x right, y down, z out)
LIGHT = LIGHT / np.linalg.norm(LIGHT)

R = CLOCK_RADIUS
DIAL_RADIUS = 0.84 * R          # inside the brass

# The parts of the hands, in pixels, measured along the hand from the centre (minus is the tail)
# The moon window: a half circle, its flat side this far above the middle, and this wide
MOON_WINDOW_Y = 0.17 * R
MOON_WINDOW_RADIUS = 0.24 * R
SYNODIC_MONTH = 29.530588853    # days from one new moon to the next
NEW_MOON = datetime.datetime(2000, 1, 6, 18, 14)    # a new moon to count from

# The calendar windows: (what strftime shows in it, how wide), their height, and how far
# below the middle they are
CALENDAR_WINDOWS = [("%a", 0.17 * R), ("%d", 0.12 * R), ("%b", 0.17 * R)]
CALENDAR_HEIGHT = 0.09 * R
CALENDAR_Y = 0.25 * R
MOTTO_Y = 0.39 * R

HOUR_LENGTH = 0.50 * R
MINUTE_LENGTH = 0.76 * R
SECOND_LENGTH = 0.80 * R
SECOND_TAIL = 0.20 * R

SECOND_SETTLE = 0.3             # seconds the seconds hand takes to jump to the next second and settle


##==================================================================
## THE BELLS
##==================================================================

SAMPLE_RATE = 44100

# Westminster Quarters, in E major: G#, F#, E and B
G_SHARP, F_SHARP, E, B = 830.61, 739.99, 659.26, 493.88
STRIKE_NOTE = 329.63            # the hour bell, E an octave below

PHRASES = [
    (G_SHARP, F_SHARP, E, B),
    (E, G_SHARP, F_SHARP, B),
    (E, F_SHARP, G_SHARP, E),
    (G_SHARP, E, F_SHARP, B),
    (B, F_SHARP, G_SHARP, E),
]

# Which phrases are played at a quarter past, half past, a quarter to and on the hour
QUARTERS = {1: (0,), 2: (1, 2), 3: (3, 4, 0), 0: (1, 2, 3, 4)}

BEAT = 0.62                     # seconds from one note to the next...
PHRASE_SECONDS = 5 * BEAT       # ...and from one phrase to the next (three short notes and a long one, then a rest)
STRIKE_GAP = 2.3                # seconds between the strokes of the hour
STRIKE_DELAY = 1.4              # extra seconds after the last phrase before the first stroke

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


# One stroke of a bell, as a numpy array of floats, peaking at about 1
def bellStroke(frequency, ringSeconds, decayScale=1.0):
    t = np.arange(int(SAMPLE_RATE * ringSeconds)) / SAMPLE_RATE
    sound = np.zeros_like(t)
    rng = np.random.default_rng(int(frequency))

    for ratio, loudness, decay in BELL_PARTIALS:
        f = frequency * ratio
        if f > SAMPLE_RATE / 2.5:
            continue
        envelope = loudness * np.exp(-t / (decay * decayScale))
        phase = rng.uniform(0, 2 * math.pi)

        # each partial is two tones very slightly apart, which beat slowly, as a real bell's do
        sound += envelope * np.sin(2 * math.pi * f * t + phase)
        sound += 0.45 * envelope * np.sin(2 * math.pi * f * 1.0013 * t + phase)

    # the tap of the hammer
    sound += 0.06 * rng.uniform(-1, 1, len(t)) * np.exp(-t / 0.003)

    attack = np.minimum(1.0, t / 0.002)             # no click at the start
    release = np.minimum(1.0, (t[-1] - t) / 0.2)    # nor at the end
    sound *= attack * release
    return sound / np.max(np.abs(sound))



# The tick or the tock of an old pendulum clock: the pallet knocking against the escape
# wheel, and the tooth dropping a moment later, each ringing the steel a little and making
# the hollow wooden case knock. The tick and the tock are not quite the same, as on a real
# clock. pitch scales the steel's ring (and the case's knock a little), and drop is the
# seconds between the two knocks.
TICK_STEEL = [(950, 0.3, 0.005), (1600, 0.12, 0.003)]   # (Hz, loudness, seconds to die away)
TICK_CASE = [(150, 1.0, 0.040), (310, 0.7, 0.028), (520, 0.45, 0.018), (820, 0.25, 0.010)]

def tickStroke(pitch, drop, dropLoudness):
    t = np.arange(int(SAMPLE_RATE * 0.15)) / SAMPLE_RATE
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
            part += amp * np.sin(2 * math.pi * f * (0.5 + 0.5 * pitch) * tt + rng.uniform(0, 6.3)) * np.exp(-tt / decay)
        sound += loudness * part * on * np.minimum(1.0, tt / 0.0003)

    sound *= np.minimum(1.0, (t[-1] - t) / 0.02)
    return sound / np.max(np.abs(sound))


# A stereo pygame Sound from a mono or stereo numpy array of floats
def makeSound(samples, volume=CHIME_VOLUME):
    if samples.ndim == 1:
        samples = np.column_stack((samples, samples))

    # a little room: a few faint, slightly late copies, different on each side
    room = samples.copy()
    for delay, gain, side in ((0.023, 0.22, 0), (0.031, 0.20, 1), (0.047, 0.14, 0), (0.059, 0.12, 1)):
        n = int(delay * SAMPLE_RATE)
        room[n:, side] += gain * samples[:-n, side]

    peak = np.max(np.abs(room))
    pcm = (room / peak * 32767 * volume).astype(np.int16)

    mixerChannels = pygame.mixer.get_init()[2]
    if mixerChannels == 1:
        pcm = pcm.mean(axis=1).astype(np.int16)

    return pygame.mixer.Sound(buffer=np.ascontiguousarray(pcm).tobytes())


# The chimes, made from their notes: {quarter: Sound}, the hour's stroke, and the tick and
# the tock. None if there is no sound.
def makeChimes():
    try:
        if not pygame.mixer.get_init():
            pygame.mixer.init(frequency=SAMPLE_RATE, size=-16, channels=2)

        if pygame.mixer.get_init()[:2] != (SAMPLE_RATE, -16):
            print(f"Clock: the mixer is set up as {pygame.mixer.get_init()}, not as the chimes need")
            return None, None, None

        notes = {f: bellStroke(f, 5.0) for f in (G_SHARP, F_SHARP, E, B)}
        pans = {G_SHARP: 0.62, F_SHARP: 0.54, E: 0.46, B: 0.38}     # spread a little, like a row of rods

        chimes = {}
        for quarter, phrases in QUARTERS.items():
            length = len(phrases) * PHRASE_SECONDS + 5.0
            mix = np.zeros((int(length * SAMPLE_RATE), 2))

            for p, phrase in enumerate(phrases):
                for n, note in enumerate(PHRASES[phrase]):
                    start = int((p * PHRASE_SECONDS + n * BEAT) * SAMPLE_RATE)
                    samples = notes[note]
                    loudness = 0.85 if n == 3 else 0.75     # the long note at the end of a phrase is a little louder
                    mix[start:start + len(samples), 0] += samples * loudness * (1 - pans[note]) * 2
                    mix[start:start + len(samples), 1] += samples * loudness * pans[note] * 2

            chimes[quarter] = makeSound(mix)

        strike = makeSound(bellStroke(STRIKE_NOTE, 7.0, decayScale=1.8))
        ticks = [makeSound(tickStroke(1.0, 0.006, 0.55), TICK_VOLUME),
                 makeSound(tickStroke(0.9, 0.009, 0.4), TICK_VOLUME)]
        return chimes, strike, ticks

    except pygame.error as exc:
        print(f"Clock: no chimes: {exc}")
        return None, None, None


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


# The light on a raised round shape, whose height at each radius is given by profile
def shadeProfile(r, ux, uy, profileR, profileH):
    slope = np.interp(r, profileR, np.gradient(profileH, profileR))
    nx, ny, nz = -slope * ux, -slope * uy, np.ones_like(r)
    length = np.sqrt(nx * nx + ny * ny + nz * nz)
    nx, ny, nz = nx / length, ny / length, nz / length

    diffuse = np.clip(nx * LIGHT[0] + ny * LIGHT[1] + nz * LIGHT[2], 0, 1)
    half = LIGHT + np.array([0, 0, 1.0])
    half = half / np.linalg.norm(half)
    specular = np.clip(nx * half[0] + ny * half[1] + nz * half[2], 0, 1) ** 60
    return diffuse, specular


# A small polished brass dome, such as the nut in the middle that holds the hands on
def brassDome(radius):
    size = int(radius * 2 + 4)
    r, ux, uy, _, _ = polarGrid(size)
    rs = np.linspace(0, radius + 2, 200)
    hs = np.sqrt(np.clip(radius * radius - rs * rs, 0, None)) * 0.8
    diffuse, specular = shadeProfile(r, ux, uy, rs, hs)
    colour = np.array(BRASS, dtype=np.float32)
    rgb = colour * (0.3 + 0.85 * diffuse)[..., None] + 255 * 0.9 * specular[..., None]
    alpha = np.clip(radius + 0.5 - r, 0, 1) * 255
    return toSurface(rgb, alpha)


# Text, with its middle at (x, y), turned by angle degrees clockwise
def blitText(surface, font, text, colour, x, y, angle=0):
    image = font.render(text, True, colour)
    if angle:
        image = pygame.transform.rotozoom(image, -angle, 1)
    surface.blit(image, image.get_rect(center=(round(x), round(y))))


def serifFont(size, italic=False):
    font = pygame.font.SysFont(FONT_NAMES, size, italic=italic)
    return font


##==================================================================
## THE BACKGROUND AND THE CLOCK FACE (drawn once)
##==================================================================

# A dark polished wood, with the clock's shadow on it
def drawBackground():
    w, h = scr.SCREEN_WIDTH, scr.SCREEN_HEIGHT
    rng = np.random.default_rng(7)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)

    # the grain runs across in fine streaks, wandering up and down, with a few broad darker bands
    wander = 18 * waves(xx * 0.3, yy, 6, 140, rng) + 5 * waves(xx, yy, 4, 40, rng)
    v = yy + wander
    rows = np.repeat(rng.normal(0, 1, (h // 2 + 40, 1)), 2, axis=0)[:, 0]
    streaks = np.interp(v, np.arange(len(rows)) - 40, rows)
    bands = np.sin(v * 0.021 + 2 * waves(xx, yy, 3, 400, rng))
    fine = rng.normal(0, 1, (h, w)) * 0.04
    shade = 0.6 + 0.07 * streaks + 0.1 * bands + 0.1 * waves(xx, yy * 3, 5, 300, rng) + fine

    dark = np.array([30, 16, 9], dtype=np.float32)
    light = np.array([86, 50, 26], dtype=np.float32)
    rgb = dark + (light - dark) * np.clip(shade, 0, 1)[..., None]

    # darker at the corners
    cx, cy = w / 2, h / 2
    corner = np.sqrt(((xx - cx) / cx) ** 2 + ((yy - cy) / cy) ** 2)
    rgb *= (1 - 0.45 * smoothstep(0.6, 1.5, corner))[..., None]

    # the clock's shadow, falling down and to the right
    sx, sy = CLOCK_CENTRE[0] + 14, CLOCK_CENTRE[1] + 20
    distance = np.sqrt((xx - sx) ** 2 + (yy - sy) ** 2)
    rgb *= (1 - 0.7 * (1 - smoothstep(R - 25, R + 35, distance)))[..., None]

    return toSurface(rgb)


# The brass case and the dial, without the hands, as a surface 2R across with see-through corners
def drawFace():
    size = 2 * R
    rng = np.random.default_rng(11)
    r, ux, uy, dx, dy = polarGrid(size)

    # --- the brass case: a rounded outer rim, a groove, and a thin bead next to the dial
    rs = np.linspace(0, R + 2, 2000)
    hs = np.zeros_like(rs)
    rimMid, rimHalf = 0.925 * R, 0.075 * R
    hs += np.sqrt(np.clip(1 - ((rs - rimMid) / rimHalf) ** 2, 0, None)) * rimHalf * 0.9
    beadMid, beadHalf = 0.86 * R, 0.014 * R
    hs += np.sqrt(np.clip(1 - ((rs - beadMid) / beadHalf) ** 2, 0, None)) * beadHalf
    diffuse, specular = shadeProfile(r, ux, uy, rs, hs)

    angle = np.arctan2(dy, dx)
    brushed = 1 + 0.05 * np.sin(angle * 900 + 3 * np.sin(angle * 7)) * rng.uniform(0.6, 1, r.shape)
    brass = np.array(BRASS, dtype=np.float32)
    caseRgb = brass * ((0.22 + 0.9 * diffuse) * brushed)[..., None] + np.array([255, 235, 190]) * (0.8 * specular)[..., None]

    # darker in the groove between the rim and the bead
    groove = np.exp(-((r - 0.847 * R) / (0.005 * R)) ** 2) + np.exp(-((r - 0.8745 * R) / (0.004 * R)) ** 2)
    caseRgb *= (1 - 0.6 * groove)[..., None]

    # --- the dial: old ivory paint, a little blotchy, darker at the edge and in the case's shadow
    yy, xx = dy, dx
    blotch = waves(xx, yy, 8, 90, rng) * 0.5 + waves(xx, yy, 6, 25, rng) * 0.25
    grain = rng.normal(0, 1, r.shape)
    ivory = np.array([236, 223, 192], dtype=np.float32)
    aged = np.array([205, 182, 138], dtype=np.float32)
    age = np.clip(0.25 + 0.18 * blotch + 0.45 * smoothstep(0.45 * R, DIAL_RADIUS, r), 0, 1)
    dialRgb = ivory + (aged - ivory) * age[..., None] + (grain * 3)[..., None]

    # the case stands up from the dial, so its shadow falls on the side away from the light
    shift = 0.022 * R
    sr = np.sqrt((dx - LIGHT[0] * -shift) ** 2 + (dy - LIGHT[1] * -shift) ** 2)
    shadow = smoothstep(DIAL_RADIUS - 0.05 * R, DIAL_RADIUS + 0.01 * R, sr)
    dialRgb *= (1 - 0.5 * shadow)[..., None]

    inDial = np.clip(DIAL_RADIUS + 0.5 - r, 0, 1)[..., None]
    rgb = dialRgb * inDial + caseRgb * (1 - inDial)
    alpha = np.clip(R - 0.5 - r, 0, 1) * 255

    face = toSurface(rgb, alpha)
    face.blit(drawDialMarks(), (0, 0))
    return face


# The face with a motto on it, below the middle, as some old clocks have
def withMotto(face, motto):
    face = face.copy()
    font = serifFont(round(0.042 * R * SS), italic=True)
    text = font.render(motto, True, INK)
    w, h = text.get_size()
    text = pygame.transform.smoothscale(text, (round(w / SS), round(h / SS)))
    face.blit(text, text.get_rect(center=(R, R + MOTTO_Y)))
    return face


# The rings, the minute marks and the numerals, drawn big and shrunk to make them smooth
def drawDialMarks():
    big = 2 * R * SS
    c = R * SS
    marks = pygame.Surface((big, big), pygame.SRCALPHA)
    marks.fill((*INK, 0))

    def ring(radius, width):
        pygame.draw.circle(marks, INK, (c, c), round(radius * SS), round(width * SS))

    def point(radius, angle):
        a = math.radians(angle)
        return c + radius * SS * math.sin(a), c - radius * SS * math.cos(a)

    # the minute track, between two rings
    outer, inner = 0.795 * R, 0.745 * R
    ring(outer, 2)
    ring(inner, 1.4)
    for minute in range(60):
        if minute % 5:
            pygame.draw.line(marks, INK, point(inner, minute * 6), point(outer, minute * 6), round(1.6 * SS))
        else:
            pygame.draw.circle(marks, INK, point((inner + outer) / 2, minute * 6), round(5 * SS))

    # a thin ring inside the numerals
    ring(0.535 * R, 1.4)
    ring(0.52 * R, 0.8)

    # the numerals, standing on the inner ring and leaning out from the middle
    font = serifFont(round(0.135 * R * SS))
    numerals = ["XII", "I", "II", "III", "IIII", "V", "VI", "VII", "VIII", "IX", "X", "XI"]
    for hour, numeral in enumerate(numerals):
        x, y = point(0.64 * R, hour * 30)
        blitText(marks, font, numeral, INK, x, y, hour * 30)

    return pygame.transform.smoothscale(marks, (2 * R, 2 * R))


# The glass over the dial: a soft reflection of the window, up and to the left
def drawGlass():
    size = 2 * R
    r, _, _, dx, dy = polarGrid(size)
    hx, hy = -0.32 * R, -0.42 * R
    glow = np.exp(-(((dx - hx) / (0.42 * R)) ** 2 + ((dy - hy) / (0.28 * R)) ** 2))
    streak = np.exp(-((dx + dy + 0.95 * R) / (0.05 * R)) ** 2) * (1 - smoothstep(0.55 * R, DIAL_RADIUS, r))
    alpha = (34 * glow + 22 * streak) * np.clip(DIAL_RADIUS - r, 0, 1)
    rgb = np.full((size, size, 3), 255, dtype=np.float32)
    return toSurface(rgb, alpha)


##==================================================================
## THE HANDS
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
# left), and y along it from the pivot (minus is the tail). The left side is drawn a little
# lighter, as though the light catches that slope of the steel.
def makeHand(length, tail, halfWidth, shapes, shadowOffset):
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

    image = render(STEEL)
    lit = render(STEEL_LIGHT)
    image.blit(lit, (0, 0), pygame.Rect(0, 0, round(pivot[0] * SS), h * SS))
    image = pygame.transform.smoothscale(image, (w, h))
    return Hand(image, pivot, shadowOffset)


# A tapering bar from y0 to y1, w0 wide at y0 and w1 wide at y1 (w1 = 0 for a point)
def taper(y0, y1, w0, w1):
    return ("poly", [(-w0 / 2, y0), (-w1 / 2, y1), (w1 / 2, y1), (w0 / 2, y0)] if w1 else
                    [(-w0 / 2, y0), (0, y1), (w0 / 2, y0)])


# Breguet hands: a slim shaft, an open ring near the end, then a fine point
def makeHands():
    L = HOUR_LENGTH
    ringY, ringR, holeR = 0.64 * L, 0.12 * L, 0.07 * L
    hour = makeHand(L, 0.12 * L, ringR + 2, [
        taper(-0.12 * L, ringY, 22, 12),
        ("disc", -0.12 * L, 12),
        ("disc", ringY, ringR),
        ("hole", ringY, holeR),
        taper(ringY + holeR, L, 16, 0),
        ("disc", 0, 20),
    ], (5, 7))

    L = MINUTE_LENGTH
    ringY, ringR, holeR = 0.76 * L, 0.06 * L, 0.035 * L
    minute = makeHand(L, 0.1 * L, ringR + 2, [
        taper(-0.1 * L, ringY, 16, 8),
        ("disc", -0.1 * L, 9),
        ("disc", ringY, ringR),
        ("hole", ringY, holeR),
        taper(ringY + holeR, L, 12, 0),
        ("disc", 0, 17),
    ], (8, 11))

    L = SECOND_LENGTH
    second = makeHand(L, SECOND_TAIL, 16, [
        taper(-SECOND_TAIL, L, 5, 1.5),
        ("disc", -0.8 * SECOND_TAIL, 13),
        ("hole", -0.8 * SECOND_TAIL, 6),
        ("disc", 0, 9),
    ], (11, 15))

    return hour, minute, second


# How far the seconds hand has got to its next mark, 0 to 1, overshooting a little and
# settling back, the way a real one jumps
def settle(fraction):
    t = min(1.0, fraction / SECOND_SETTLE) * 3.3
    return 1 - math.exp(-2.4 * t) * math.cos(3.1 * t)


##==================================================================
## THE MOON AND THE CALENDAR WINDOWS
##==================================================================

# How far through its month the moon is: 0 new, 0.25 first quarter, 0.5 full...
def moonPhase(now):
    days = (now - NEW_MOON).total_seconds() / 86400
    return (days / SYNODIC_MONTH) % 1


# The moon window, as on an old longcase clock: a big disc painted with a night sky and two
# moons turns slowly behind a half-round window, whose two humps hide the moon as it comes
# and goes, making its phases. Returns the window's picture and where its flat side's
# middle is in it.
def drawMoonWindow(phase):
    a = MOON_WINDOW_RADIUS
    w, h = int(2 * a + 10), int(a + 10)
    ox, oy = w / 2, a + 5
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    x, y = xx + 0.5 - ox, yy + 0.5 - oy

    # the window: inside the half circle, but not in either hump (minus inside, plus outside)
    edge = np.maximum.reduce([np.hypot(x, y) - a, y,
                              a / 2 - np.hypot(x + a / 2, y), a / 2 - np.hypot(x - a / 2, y)])
    inside = np.clip(0.5 - edge, 0, 1)

    # the disc turns about a point well below the window; the moon crosses from left to
    # right, peeping out from behind the left hump as it waxes and going behind the right one
    # as it wanes
    turn = 2.5 * a
    pivotY = -a / 2 + turn
    angle = math.asin((phase - 0.5) * 2.6 * a / turn)
    mx, my = turn * math.sin(angle), pivotY - turn * math.cos(angle)

    # the sky, a little lighter towards the bottom, with stars painted on the disc
    rgb = np.empty((h, w, 3), dtype=np.float32)
    rgb[:] = SKY
    rgb *= (0.8 + 0.35 * np.clip((y + a) / a, 0, 1))[..., None]
    rng = np.random.default_rng(3)
    for _ in range(90):
        sa = rng.uniform(-math.pi, math.pi) + angle
        sr = rng.uniform(turn - 1.1 * a, turn + 0.2 * a)
        sx, sy = sr * math.sin(sa), pivotY - sr * math.cos(sa)
        size = rng.uniform(0.6, 1.4)
        glow = np.exp(-((x - sx) ** 2 + (y - sy) ** 2) / (size * size))
        rgb += glow[..., None] * np.array([235, 215, 150], dtype=np.float32)

    # the moon, gold, a little rounded by the light, with a few darker seas
    radius = a / 2 * 0.94
    dx, dy = x - mx, y - my
    dist = np.hypot(dx, dy)
    moon = np.clip(radius - dist + 0.5, 0, 1)
    dome = np.sqrt(np.clip(1 - (dist / radius) ** 2, 0, 1))
    lit = 0.65 + 0.35 * np.clip((-dx * 0.5 - dy * 0.6) / radius + dome, 0, 1.2)
    seas = np.zeros_like(x)
    for sx, sy, sr in ((-0.3, -0.25, 0.28), (0.25, 0.1, 0.22), (-0.1, 0.35, 0.18), (0.35, -0.35, 0.12)):
        seas += np.exp(-((dx / radius - sx) ** 2 + (dy / radius - sy) ** 2) / (sr * sr))
    moonRgb = np.array(MOON, dtype=np.float32) * (lit * (1 - 0.18 * np.clip(seas, 0, 1)))[..., None]
    rgb = rgb * (1 - moon[..., None]) + moonRgb * moon[..., None]

    # set back into the dial, so darker near the edge of the window, which is outlined
    rgb *= (1 - 0.55 * np.exp(np.minimum(edge, 0) / 5))[..., None]
    outline = np.clip(1.6 - np.abs(edge + 0.4), 0, 1)
    rgb = rgb * (1 - outline[..., None]) + np.array(INK, dtype=np.float32) * outline[..., None]
    alpha = np.maximum(inside, outline) * 255

    return toSurface(rgb, alpha), (ox, oy)


# The three little windows of the calendar, side by side: the day, the date and the month,
# printed on wheels behind the dial. Returns their picture.
def drawCalendar(now):
    gap = round(0.025 * R)
    height = round(CALENDAR_HEIGHT)
    widths = [round(width) for _, width in CALENDAR_WINDOWS]
    surface = pygame.Surface((sum(widths) + gap * (len(widths) - 1), height), pygame.SRCALPHA)
    surface.fill((0, 0, 0, 0))
    font = serifFont(round(0.062 * R))

    # each wheel is round, so darker towards its top and bottom, and the dial's edge shades its top
    yy = (np.arange(height) + 0.5) / height * 2 - 1
    shade = (1 - 0.3 * yy ** 2) * (1 - 0.45 * np.exp(-(np.arange(height) / 4.0)))

    x = 0
    for (fmt, _), width in zip(CALENDAR_WINDOWS, widths):
        rgb = np.empty((height, width, 3), dtype=np.float32)
        rgb[:] = CARD
        rgb *= shade[:, None, None]
        card = toSurface(rgb)
        text = now.strftime(fmt).upper()
        image = font.render(text, True, INK)
        card.blit(image, image.get_rect(center=(width / 2, height / 2 + 1)))
        surface.blit(card, (x, 0))
        pygame.draw.rect(surface, INK, (x, 0, width, height), 2)
        x += width + gap

    return surface


# The face with the day's moon and calendar on it
def withWindows(face, now):
    face = face.copy()
    moon, (ox, oy) = drawMoonWindow(moonPhase(now))
    face.blit(moon, (round(R - ox), round(R - MOON_WINDOW_Y - oy)))
    calendar = drawCalendar(now)
    face.blit(calendar, calendar.get_rect(center=(R, R + CALENDAR_Y)))
    return face


##==================================================================
## THE SCREEN
##==================================================================

# What the OK button goes round: (chimes, ticking, what is shown under the date)
SOUND_CHOICES = [
    (True, True, "Chimes and ticking"),
    (True, False, "Chimes only"),
    (False, True, "Ticking only"),
    (False, False, "Sound off"),
]

class ClockScreen(scr.Screen):

    name = "CLOCK"

    def start(self):
        self.wood = drawBackground()
        face = drawFace()
        self.faces = {motto: withMotto(face, motto) for motto in (MOTTO, EVENING_MOTTO)}
        self.dayFaces = None            # the faces with today's moon and calendar on them
        self.glass = drawGlass()
        self.nut = brassDome(13)
        self.hour, self.minute, self.second = makeHands()
        self.statusFont = serifFont(30, italic=True)

        self.date = None                # the date of the moon and the calendar on the dial
        self.background = self.wood
        self.clockImage = None          # the clock as last drawn, and the time it shows
        self.clockKey = None
        self.visible = False

        self.chimes, self.strike, self.ticks = makeChimes() if CHIME else (None, None, None)
        self.lastQuarter = self.quarterKey(datetime.datetime.now())    # no chime at the start
        self.strikesDue = []            # pygame ticks at which the hour is still to be struck
        self.choice = 0                 # which of SOUND_CHOICES, changed with the OK button
        self.lastSecond = None          # the second last ticked
        self.status = None              # the words under the date, and their picture
        self.statusImage = None


    def enter(self):
        self.visible = True


    # The ticking stops; the bells too, unless they are meant to be heard behind the other screens
    def leave(self):
        self.visible = False
        if not CHIME_WHEN_HIDDEN:
            self.silence()


    def silence(self):
        self.strikesDue = []
        for sound in list((self.chimes or {}).values()) + [self.strike] + (self.ticks or []):
            if sound:
                sound.stop()


    @property
    def chimesOn(self):
        return SOUND_CHOICES[self.choice][0]

    @property
    def tickOn(self):
        return SOUND_CHOICES[self.choice][1]


    # OK (pressed briefly) goes on to the next of SOUND_CHOICES; held down, it plays the last quarter again
    def handleEvent(self, event):
        if event.type == scr.OK_PRESSED or (event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_SPACE)):
            self.choice = (self.choice + 1) % len(SOUND_CHOICES)
            print(f"Clock: {SOUND_CHOICES[self.choice][2]}")
            if not self.chimesOn:
                self.silence()

        elif event.type == scr.OK_HELD or (event.type == pygame.KEYDOWN and event.key == pygame.K_DELETE):
            now = datetime.datetime.now()
            self.silence()
            self.chime(now.hour, now.minute // 15)


    # Whether it is the time of night when the clock is silent
    @staticmethod
    def quietTime(now):
        if QUIET_FROM <= QUIET_UNTIL:
            return QUIET_FROM <= now.hour < QUIET_UNTIL
        return now.hour >= QUIET_FROM or now.hour < QUIET_UNTIL


    # The words in the corner: what the OK button has chosen, and at night that the clock is silent
    def statusFor(self, now):
        if not self.chimes:
            return None
        words = SOUND_CHOICES[self.choice][2]
        if self.quietTime(now):
            words += f" \u2013 silent until {QUIET_UNTIL % 12 or 12}{'AM' if QUIET_UNTIL < 12 else 'PM'}"
        return words


    # The quarter of an hour it is, if it has just started, otherwise None
    @staticmethod
    def quarterKey(now):
        if now.minute % 15 == 0 and now.second < 10:
            return (now.date(), now.hour, now.minute)
        return None


    def chime(self, hour, quarter):
        if not self.chimes:
            return

        quarter %= 4
        self.chimes[quarter].play()

        if quarter == 0 and STRIKE_HOURS:
            first = pygame.time.get_ticks() + (4 * PHRASE_SECONDS + STRIKE_DELAY) * 1000
            strokes = hour % 12 or 12
            self.strikesDue = [first + i * STRIKE_GAP * 1000 for i in range(strokes)]


    def update(self, visible):
        now = datetime.datetime.now()

        quiet = self.quietTime(now)

        key = self.quarterKey(now)
        if key is not None and key != self.lastQuarter:
            self.lastQuarter = key
            if self.chimesOn and not quiet and (visible or CHIME_WHEN_HIDDEN):
                self.chime(now.hour, now.minute // 15)

        ticks = pygame.time.get_ticks()
        while self.strikesDue and ticks >= self.strikesDue[0]:
            self.strikesDue.pop(0)
            self.strike.play()

        if not visible:
            return

        # tick, tock, as the seconds hand moves
        if now.second != self.lastSecond:
            self.lastSecond = now.second
            if self.tickOn and not quiet and self.ticks:
                self.ticks[now.second % 2].play()

        status = self.statusFor(now)
        if status != self.status:
            self.status = status
            self.statusImage = self.statusFont.render(status, True, TEXT_COLOUR) if status else None

        if now.date() != self.date:
            self.date = now.date()
            self.dayFaces = {motto: withWindows(face, now) for motto, face in self.faces.items()}
            self.clockKey = None

        # the seconds hand moves for a moment after each second, then is still till the next
        fraction = now.microsecond / 1e6
        moving = fraction < SECOND_SETTLE
        clockKey = (now.hour, now.minute, now.second, round(fraction, 2) if moving else None)
        if clockKey != self.clockKey:
            self.clockKey = clockKey
            self.clockImage = self.drawClock(now, settle(fraction))


    # The clock area of the background, with the face and the hands drawn on it
    def drawClock(self, now, settled):
        area = pygame.Rect(0, 0, 2 * R, 2 * R)
        area.center = CLOCK_CENTRE
        image = self.background.subsurface(area).copy()
        image.blit(self.dayFaces[EVENING_MOTTO if now.hour >= EVENING_FROM else MOTTO], (0, 0))

        seconds = now.second + now.microsecond / 1e6
        minutes = now.minute + seconds / 60
        hours = now.hour % 12 + minutes / 60
        tick = now.second - 1 + settled

        centre = (R, R)
        self.hour.draw(image, hours * 30, centre)
        self.minute.draw(image, minutes * 6, centre)
        self.second.draw(image, tick * 6, centre)
        image.blit(self.nut, self.nut.get_rect(center=centre))
        image.blit(self.glass, (0, 0))
        return image


    def draw(self, surface):
        surface.blit(self.background, (0, 0))
        area = self.clockImage.get_rect(center=CLOCK_CENTRE)
        surface.blit(self.clockImage, area)
        if self.statusImage:
            surface.blit(self.statusImage, self.statusImage.get_rect(bottomright=STATUS_CORNER))
