"""
biomonitor.py

A screen like the sickbay biomonitor: a row of dials (temperature, brain, lungs, cell
rate and two for the blood), each with a pointer that drifts about in its normal range,
and between them two red lamps that flash with the breathing and the pulse. The pulse
lamp plays a heartbeat each time it flashes, while the screen is shown.

The dials never change, so they are drawn once, when the program starts, with an old
film look (warm tint, dark corners and a soft haze), and only the lamps and the pointers
are drawn over them each frame.

Its files are in this folder:

    impact.ttf              the font the dials' numbers and labels are drawn in
    warm_white_arrow.png    the pointer
    heartbeat.mp3           the heartbeat (none is played if it can't be loaded)

Uses numpy (on Raspberry Pi OS already; otherwise sudo apt install python3-numpy).
"""

import math
import os
import random
import pygame
import numpy as np
import screens as scr

##==================================================================
## CONFIGURATION
##==================================================================

FOLDER = os.path.dirname(os.path.abspath(__file__))
FONT_FILE = os.path.join(FOLDER, "impact.ttf")
ARROW_FILE = os.path.join(FOLDER, "warm_white_arrow.png")
HEARTBEAT_FILE = os.path.join(FOLDER, "heartbeat.mp3")

FONT_SIZE_1 = 22
FONT_SIZE_2 = 28

DIAL_TOP = 100
DIAL_HEIGHT = 800
DIAL_BOTTOM = DIAL_TOP + DIAL_HEIGHT
DIAL_MARGIN = 170
DIAL_SPACING = 270

RESPIRATION_RATE = 18       # flashes a minute of the breathing lamp...
PULSE_RATE = 72             # ...and of the pulse lamp

BACKGROUND_COLOUR = (10, 10, 10)
BLACK = BACKGROUND_COLOUR
WHITE = (255, 255, 255)
RED = (255, 50, 50)
YELLOW = (180, 150, 50)
GREEN = (100, 255, 100)
LAMP_COLOUR = (220, 50, 50)
GAMMA = 3.5


##==================================================================
## GAUGE DEFINITIONS
##==================================================================

# Deriving C from F keeps the band edges aligned between the two scales. The
# hand-entered 35.7 was about 7px out against the central bar; this fixes it.
TEMP_F_BANDS = (96.4, 97.0, 98.0, 99.2)
TEMP_C_BANDS = tuple((f - 32.0) * 5.0 / 9.0 for f in TEMP_F_BANDS)

# Each gauge sits in a slot: x = DIAL_MARGIN + slot * DIAL_SPACING.
# Slot 3 is the empty centre column where the waveforms go.
#
# Per scale:
#   scale       (min, max) of the numeric range
#   bands       (red1, yellow1, green, yellow2) thresholds
#   minor/major tick spacing
#   label_step  spacing for numbers, if different from major
#   style       which side the ticks stick out: LEFT / RIGHT / BOTH
#   bar         draw the banded spine for this scale
#   num_dx      x offset of the numbers relative to the gauge centre
#   digits      how many trailing characters of the number to show
#   subs        value -> "before*after" split-font overrides
#   fives_dx    x offset for half-major '5' labels, omit for none
#   side_bar    bar to left of dial showing normal range
# Footer entries are (dx, dy, text, font_size, align), dy from DIAL_BOTTOM.
# The pointer is (lowest, highest, speed, randomness): it wanders between the lowest and
# highest values on the first scale.

GAUGES = [
    dict(slot=0, scales=[
            dict(scale=(89.0, 106.0), bands=TEMP_F_BANDS, minor=0.1, major=1.0,
                 style="LEFT", bar=True, num_dx=-15, digits=1,
                 subs={90: "9*0", 95: "9*5", 100: "10*0", 105: "10*5"}),
            dict(scale=(31.7, 41.1), bands=TEMP_C_BANDS, minor=0.1, major=1.0,
                 style="RIGHT", bar=False, num_dx=40, digits=2),
         ],
         footer=[(0, 30, "TEMP", 2, "CENTER"),
                 (-35, 60, "F", 1, "CENTER"),
                 (35, 60, "C", 1, "CENTER")],
         pointer=(95.0, 101.0, 0.002, 0.005)),

    dict(slot=1, scales=[
            dict(scale=(0, 140), bands=(54, 60, 82, 93), minor=1, major=10,
                 style="BOTH", bar=True, num_dx=-15, digits=2,
                 subs={0: "0*0", 100: "10*0"}),
         ],
         sidebar=(62, 80),
         footer=[(0, 32, "BRAIN", 2, "CENTER"),
                 (-35, 65, "K", 2, "CENTER"),
                 (-18, 70, "3", 1, "CENTER")],
         pointer=(62, 80, 0.005, 0.02)),

    dict(slot=2, scales=[
            dict(scale=(0, 36), bands=(11.5, 15.8, 21.6, 25), minor=1, major=2,
                 style="BOTH", bar=True, num_dx=-15, digits=1,
                 subs={0: "0*0", 10: "1*0", 20: "2*0", 30: "3*0"}),
         ],
         sidebar=(16, 21.2),
         footer=[(0, 32, "LUNGS", 2, "CENTER")],
         pointer=(16, 21.2, 0.01, 0.03)),

    dict(slot=4, scales=[
            dict(scale=(20, 65), bands=(33.5, 37, 45, 51), minor=1, major=5,
                 label_step=10, style="BOTH", bar=True, num_dx=-15, digits=2,
                 fives_dx=10)
         ],
         sidebar=(37, 45),
         footer=[(0, 32, "CELL", 2, "CENTER"),
                 (0, 65, "RATE", 2, "CENTER")],
         pointer=(37, 45, 0.025, 0.025)),

    dict(slot=5, scales=[
            dict(scale=(50, 185), bands=(89, 107, 135, 152), minor=2, major=10,
                 style="BOTH", bar=True, num_dx=-15, digits=2,
                 subs={100: "1*00"}),
         ],
         sidebar=(110, 135),
         footer=[(0, 32, "BLOOD", 2, "CENTER"),
                 (-35, 65, "Q", 2, "CENTER"),
                 (-20, 60, "5", 1, "CENTER")],
         pointer=(110, 135, 0.01, 0.015)),

    dict(slot=6, scales=[
            dict(scale=(0, 16), bands=(4.2, 5.6, 9.6, 10.8), minor=0.5, major=1,
                 style="BOTH", bar=True, num_dx=-15, digits=2, fives_dx=7),
         ],
         sidebar=(6, 9.5),
         footer=[(0, 32, "BLOOD", 2, "CENTER"),
                 (-35, 65, "T", 2, "CENTER"),
                 (-20, 60, "2", 1, "CENTER"),
                 (40, 67, "x10", 1, "RIGHT")],
         pointer=(6, 9.5, 0.003, 0.005))]


# (y, text, font_size)
CENTRE_LABELS = [
    (210, "RESPIRATION", 2),
    (525, "PULSE", 2),
    (650, "ADJUST", 1),
    (674, "FOR NORMAL", 1),
    (770, "RECORDER", 1),
]


##==================================================================
## INDICATOR LAMP (for the pulse and the respiration)
##==================================================================

class IndicatorLamp:

    def __init__(self, x, y, beats_per_minute, sound=None):
        if beats_per_minute <= 0:
            raise ValueError("beats_per_minute must be positive")

        self.x = x
        self.y = y
        self.diameter = 100
        self.beats_per_minute = beats_per_minute
        self.sound = sound          # played at the start of each beat, or None

        self.t = 0.0                # how far into the beats, in seconds
        self.percent = 0            # how bright it is, 0 to 100
        self.lamp, self.lampSize = self.buildLamp()


    # Solid red disc, soft edge, with baked-in per-pixel noise for grain.
    # Built once - the noise pattern is static, not animated.
    def buildLamp(self):
        radius = self.diameter / 2
        edgeSoftness = 5            # pixels over which the edge fades, not a big halo
        size = int((radius + edgeSoftness) * 2)

        yy, xx = np.mgrid[0:size, 0:size]
        cx = cy = size / 2
        dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)

        # solid disc: 1.0 inside radius, fades to 0 only across edgeSoftness pixels
        edge = np.clip((radius + edgeSoftness - dist) / edgeSoftness, 0, 1)

        # grain: random per-pixel multiplier, subtle
        noise = np.random.default_rng().uniform(0.75, 1.0, size=(size, size))
        intensity = np.clip(edge * noise, 0, 1)

        r, g, b = LAMP_COLOUR
        arr = np.zeros((size, size, 4), dtype=np.uint8)
        arr[:, :, 0] = r
        arr[:, :, 1] = g
        arr[:, :, 2] = b
        arr[:, :, 3] = (intensity * 255).astype(np.uint8)

        surf = pygame.image.frombuffer(arr.tobytes(), (size, size), "RGBA").convert_alpha()
        return surf, size


    # Start again at the beginning of a beat (dark), e.g. when the screen is shown again
    def restart(self):
        self.t = 0.0
        self.percent = 0


    # Move on by dt seconds, playing the sound if a new beat has started
    def update(self, dt):
        period = 60.0 / self.beats_per_minute
        before = int(self.t // period)
        self.t += dt
        phase = (self.t % period) / period

        raw = (1 - math.cos(2 * math.pi * phase)) / 2   # smooth 0..1 bump
        self.percent = (raw ** (1.0 / GAMMA)) * 100

        if self.sound is not None and int(self.t // period) != before:
            self.sound.play()


    def draw(self, surface):
        self.lamp.set_alpha(int(max(0, min(255, self.percent * 2.55))))
        half = self.lampSize / 2
        surface.blit(self.lamp, (self.x - half, self.y - half))


##==================================================================
## POINTER (one per dial)
##==================================================================

class Pointer:

    def __init__(self, x, min_y, max_y, speed, randomness):
        self.x = x
        self.position = DIAL_BOTTOM
        self.target = DIAL_BOTTOM
        self.min_y = min_y
        self.max_y = max_y
        self.randomness = randomness    # the chance each frame of choosing a new target
        self.speed = speed
        self.velocity = 0.0
        self.accel = 400.0              # pixels/sec^2 - tune this
        self.damping = 0.7


    # One frame: accelerate toward the target, then damp
    def update(self):
        offset = self.target - self.position
        self.velocity += offset * self.accel * self.speed
        self.velocity *= self.damping
        self.position += self.velocity * self.speed

        # don't allow overshoots
        self.position = max(DIAL_TOP + 10, min(DIAL_BOTTOM - 10, self.position))

        # Choose a new random target
        if random.random() < self.randomness:
            self.target = random.uniform(self.min_y, self.max_y)


    def draw(self, surface, arrow):
        surface.blit(arrow, (self.x, self.position - 25))


##==================================================================
## SCALE GEOMETRY
##==================================================================

def get_y(value, scale_min, scale_max):
    """Map a value onto a screen y within the dial, clamped to the scale."""
    value = max(scale_min, min(scale_max, value))

    # fraction of the way up the scale (0.0 at scale_min, 1.0 at scale_max)
    frac = (value - scale_min) / (scale_max - scale_min)

    # convert to a pixel offset from the bottom, then to a screen y
    return DIAL_BOTTOM - frac * DIAL_HEIGHT


def ticks(scale_min, scale_max, step):
    """Grid values that are multiples of `step` and lie within the scale.

    Indexes off the global grid rather than accumulating, so float drift can't
    creep in over a long minor scale, and a tick can never overshoot the top.
    """
    first = math.ceil(round(scale_min / step, 9))
    last = math.floor(round(scale_max / step, 9))
    return [i * step for i in range(first, last + 1)]


def get_colour(value, colour_bands):
    """Pick the band colour a value falls into."""
    (red1_band, yellow1_band, green_band, yellow2_band) = colour_bands

    if value < red1_band:
        return RED
    elif value < yellow1_band:
        return YELLOW
    elif value < green_band:
        return GREEN
    elif value < yellow2_band:
        return YELLOW
    else:
        return RED


##==================================================================
## DRAWING PRIMITIVES (all onto the background, once)
##==================================================================

def draw_vertical_bar(surface, x, scale_min, scale_max, colour_bands):
    """The banded spine of the gauge, bottom to top."""
    (red1_band, yellow1_band, green_band, yellow2_band) = colour_bands

    y1 = get_y(red1_band, scale_min, scale_max)
    pygame.draw.line(surface, RED, (x, DIAL_BOTTOM), (x, y1), 5)

    y2 = get_y(yellow1_band, scale_min, scale_max)
    pygame.draw.line(surface, YELLOW, (x, y1), (x, y2), 5)

    y3 = get_y(green_band, scale_min, scale_max)
    pygame.draw.line(surface, GREEN, (x, y2), (x, y3), 5)

    y4 = get_y(yellow2_band, scale_min, scale_max)
    pygame.draw.line(surface, YELLOW, (x, y3), (x, y4), 5)

    pygame.draw.line(surface, RED, (x, y4), (x, DIAL_TOP), 5)


def draw_lines(surface, x, minor_scale, major_scale, scale_min, scale_max, style, colour_bands):
    """Minor and major tick marks, coloured by band."""
    for step, (inner, outer, width) in ((minor_scale, (3, 8, 1)), (major_scale, (3, 12, 2))):
        for value in ticks(scale_min, scale_max, step):
            y = get_y(value, scale_min, scale_max)
            colour = get_colour(value, colour_bands)
            if style == "LEFT":
                pygame.draw.line(surface, colour, (x - inner, y), (x - outer, y), width)
            elif style == "RIGHT":
                pygame.draw.line(surface, colour, (x + inner, y), (x + outer, y), width)
            else:
                pygame.draw.line(surface, colour, (x - outer, y), (x + outer, y), width)


def draw_sidebar(surface, x, scale_min, scale_max, bottom, top):
    y1 = get_y(bottom, scale_min, scale_max)
    y2 = get_y(top, scale_min, scale_max)

    pygame.draw.line(surface, GREEN, (x, y1), (x, y2), 6)
    pygame.draw.line(surface, GREEN, (x, y1), (x - 7, y1), 1)
    pygame.draw.line(surface, GREEN, (x, y2), (x - 7, y2), 1)


def add_text(surface, x, y, text, font, colour, align):
    """Blit text anchored horizontally by `align`, vertically centred on y."""
    text_surf = font.render(text, True, colour)
    text_rect = text_surf.get_rect()

    if align == "LEFT":
        text_rect.left = x
    elif align == "RIGHT":
        text_rect.right = x
    else:
        text_rect.centerx = x

    text_rect.centery = y
    surface.blit(text_surf, text_rect)


def add_numbers(surface, fonts, x, scale_min, scale_max, major_scale, colour_bands, digits, substitutes):
    """Numeric labels on the major scale.

    `digits` keeps only the trailing N characters (the TOS dials show '0' where
    a modern gauge would show '100'). `substitutes` overrides that for chosen
    values, splitting on '*' to render the leading part in the larger font.
    """
    for value in ticks(scale_min, scale_max, major_scale):
        y = get_y(value, scale_min, scale_max)
        colour = get_colour(value, colour_bands)

        if value in substitutes:
            before, after = substitutes[value].split("*")
            add_text(surface, x, y, after, fonts[1], colour, "RIGHT")
            # measure rather than assume a fixed glyph width, so changing the
            # font or size can't pull the two halves of the number apart
            add_text(surface, x - fonts[1].size(after)[0], y, before, fonts[2], colour, "RIGHT")
        else:
            add_text(surface, x, y, format(value, ".0f")[-digits:], fonts[1], colour, "RIGHT")


def add_fives(surface, fonts, x, scale_min, scale_max, major_scale, colour_bands):
    """Add a '5' at the half-major positions, right of the dial."""
    for value in ticks(scale_min, scale_max, major_scale):
        value -= major_scale / 2
        if scale_min <= value <= scale_max:
            y = get_y(value, scale_min, scale_max)
            add_text(surface, x + 17, y, "5", fonts[1], get_colour(value, colour_bands), "RIGHT")


def draw_lozenge(surface, x, y, width, height, col, text, font, solid):
    x1 = x - width / 2 + height / 2
    x2 = x + width / 2 - height / 2
    y1 = y - height / 2
    y2 = y + height / 2 - 1

    if solid:
        pygame.draw.circle(surface, col, (x1, y), height / 2, 0, False, True, True, False)
        pygame.draw.circle(surface, col, (x2, y), height / 2, 0, True, False, False, True)
        pygame.draw.rect(surface, col, (x1, y1, width - height, height), 0)
        if text:
            add_text(surface, x, y - 1, text, font, BLACK, "CENTER")
    else:
        pygame.draw.circle(surface, col, (x1, y), height / 2, 2, False, True, True, False)
        pygame.draw.circle(surface, col, (x2, y), height / 2, 2, True, False, False, True)
        pygame.draw.line(surface, col, (x1, y1), (x2, y1), 2)
        pygame.draw.line(surface, col, (x1, y2), (x2, y2), 2)
        if text:
            add_text(surface, x, y - 1, text, font, col, "CENTER")


##==================================================================
## VINTAGE EFFECTS
##==================================================================

def apply_vintage_tone(surface, warm_tint=(4, 4, 0), vignette_strength=0.7):
    """Lift blacks, add a warm tint, darken the corners. Vectorised with
    numpy since this touches every pixel and only runs once at start."""
    w, h = surface.get_size()
    arr = pygame.surfarray.array3d(surface).astype(np.float32)  # shape (w, h, 3)

    # warm tint: push red/green up slightly, pull blue down
    arr[:, :, 0] += warm_tint[0]
    arr[:, :, 1] += warm_tint[1]
    arr[:, :, 2] += warm_tint[2]

    # vignette
    xs = np.arange(w).reshape(w, 1)
    ys = np.arange(h).reshape(1, h)
    cx, cy = w / 2.0, h / 2.0
    max_dist = math.hypot(cx, cy)
    dist = np.sqrt((xs - cx) ** 2 + (ys - cy) ** 2) / max_dist
    vignette = np.clip(1.0 - vignette_strength * np.clip(dist - 0.35, 0, None), 0.0, 1.0)
    arr *= vignette[:, :, None]

    arr = np.clip(arr, 0, 255).astype(np.uint8)
    pygame.surfarray.blit_array(surface, arr)


def apply_film_haze(surface, haze_strength=20, blur_downscale=4):
    """Soft overall glow, like light bleeding through an old film print.
    Cheap blur trick: shrink, then scale back up, then blend additively."""
    w, h = surface.get_size()
    small = pygame.transform.smoothscale(surface, (w // blur_downscale, h // blur_downscale))
    blurred = pygame.transform.smoothscale(small, (w, h))
    blurred.set_alpha(haze_strength)  # 0-255, higher = hazier
    surface.blit(blurred, (0, 0), special_flags=pygame.BLEND_RGB_ADD)


def apply_vintage_effect(surface):
    apply_vintage_tone(surface)
    apply_film_haze(surface)


##==================================================================
## CREATE BACKGROUND
##==================================================================

def draw_scale(surface, fonts, x, spec):
    """Render one scale of one gauge from its spec dict."""
    scale_min, scale_max = spec["scale"]
    bands = spec["bands"]

    if spec.get("bar"):
        draw_vertical_bar(surface, x, scale_min, scale_max, bands)

    draw_lines(surface, x, spec["minor"], spec["major"], scale_min, scale_max, spec["style"], bands)

    step = spec.get("label_step", spec["major"])
    add_numbers(surface, fonts, x + spec["num_dx"], scale_min, scale_max, step, bands,
                spec["digits"], spec.get("subs", {}))

    if "fives_dx" in spec:
        add_fives(surface, fonts, x + spec["fives_dx"], scale_min, scale_max, step, bands)


# The dials and labels, which never change. Returns the background and a pointer for each dial.
def create_background(fonts):
    surface = pygame.Surface((scr.SCREEN_WIDTH, scr.SCREEN_HEIGHT))
    surface.fill(BACKGROUND_COLOUR)
    pointers = []

    for gauge in GAUGES:
        x = DIAL_MARGIN + gauge["slot"] * DIAL_SPACING

        for spec in gauge["scales"]:
            draw_scale(surface, fonts, x, spec)

        for dx, dy, text, size, align in gauge["footer"]:
            add_text(surface, x + dx, DIAL_BOTTOM + dy, text, fonts[size], YELLOW, align)

            # add the right hand marker to the temp gauge
            if text == "TEMP":
                y = get_y(36.5, 31.7, 41.1)
                pygame.draw.line(surface, GREEN, (x + 15, y), (x + 36, y), 5)

            if text == "LUNGS":
                y1 = get_y(14, 0, 36)
                for i in range(0, 9):
                    y2 = y1 - 20
                    col = GREEN if 2 <= i < 7 else YELLOW
                    pygame.draw.line(surface, col, (x + 25, y1), (x + 25, y2), 10)
                    y1 = y2 - 3

        # the sidebar and the pointer go by the first scale
        spec = gauge["scales"][0]
        scale_min, scale_max = spec["scale"]

        if "sidebar" in gauge:
            draw_sidebar(surface, x - 55, scale_min, scale_max, *gauge["sidebar"])

        lowest, highest, speed, randomness = gauge["pointer"]
        pointers.append(Pointer(x + 40, get_y(lowest, scale_min, scale_max),
                                get_y(highest, scale_min, scale_max), speed, randomness))

    for y, text, size in CENTRE_LABELS:
        add_text(surface, scr.SCREEN_WIDTH / 2, y, text, fonts[size], YELLOW, "CENTER")

    draw_lozenge(surface, scr.SCREEN_WIDTH / 2 - 35, 805, 50, 30, GREEN, "ON", fonts[1], False)
    draw_lozenge(surface, scr.SCREEN_WIDTH / 2 + 35, 805, 50, 30, YELLOW, None, None, False)
    draw_lozenge(surface, scr.SCREEN_WIDTH / 2, 930, 70, 40, RED, "TEST", fonts[2], True)

    apply_vintage_effect(surface)
    return surface, pointers


# The bundled TTF, so that Windows and the Pi look the same, or the default font if it isn't there
def load_font(size):
    try:
        return pygame.font.Font(FONT_FILE, size)
    except (pygame.error, OSError) as exc:
        print(f"Could not load the font {FONT_FILE}: {exc} - using the default font instead")
        return pygame.font.Font(None, size)


# The heartbeat, or None if there is no sound
def load_sound(path):
    try:
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        return pygame.mixer.Sound(path)
    except (pygame.error, OSError) as exc:
        print(f"No heartbeat sound: {exc}")
        return None


##==================================================================
## THE SCREEN
##==================================================================

class BiomonitorScreen(scr.Screen):

    name = "BIOMONITOR"
    hasSound = True

    def soundList(self):
        return [(self.heartbeat, 1.0)]

    # No heartbeat while its sound is off
    def setSound(self, on):
        self.pulse.sound = self.heartbeat if on else None

    def start(self):
        random.seed()
        fonts = {1: load_font(FONT_SIZE_1), 2: load_font(FONT_SIZE_2)}

        self.background, self.pointers = create_background(fonts)
        self.arrow = pygame.image.load(ARROW_FILE).convert_alpha()

        self.respiration = IndicatorLamp(scr.SCREEN_WIDTH / 2, 135, RESPIRATION_RATE)
        self.heartbeat = load_sound(HEARTBEAT_FILE)
        self.pulse = IndicatorLamp(scr.SCREEN_WIDTH / 2, 450, PULSE_RATE, self.heartbeat if self.soundOn else None)
        self.lastTicks = pygame.time.get_ticks()


    # The lamps start a fresh beat, rather than jumping on by however long it was hidden
    def enter(self):
        self.respiration.restart()
        self.pulse.restart()
        self.lastTicks = pygame.time.get_ticks()


    # Only moves while it is shown, so the heartbeat isn't heard behind the other screens
    def update(self, visible):
        if not visible:
            return

        now = pygame.time.get_ticks()
        dt = (now - self.lastTicks) / 1000.0
        self.lastTicks = now

        self.respiration.update(dt)
        self.pulse.update(dt)

        for pointer in self.pointers:
            pointer.update()


    def draw(self, surface):
        surface.blit(self.background, (0, 0))
        self.respiration.draw(surface)
        self.pulse.draw(surface)

        for pointer in self.pointers:
            pointer.draw(surface, self.arrow)
