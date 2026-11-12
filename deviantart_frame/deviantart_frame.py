"""
deviantart_frame.py

A screen that shows pictures from DeviantArt, one after another in a random order,
each fading into the next. A picture is zoomed to fill the whole screen, and the edges
that don't fit are cut off (or with FILL_SCREEN False, it is made as big as will fit
without cutting any of it off, on a black background).

The pictures are kept in PICTURE_FOLDER (a "pictures" folder next to this script, unless
it is changed below), in two folders inside it:

    pictures/deviantart 40 new pictures downloaded every day, keeping the newest 400;
                        which ones (artists, topics, tags, mature or not) is chosen
                        in deviantart_choices.txt
                        (see deviantart_library.py, which also says how to get the
                        DeviantArt key it needs)
    pictures/my_own     your own pictures (and any folders you make inside it), shown
                        mixed in with them only if OWN_PICTURES is True

Pictures added or taken away are noticed each time it has been round them all, so
there is no need to restart.

A picture with a credits.json in its folder (as the downloaded ones have) has its
credit (title and artist) shown in the corner.

If Pillow is installed (sudo apt install python3-pil, or pip install pillow), photos
taken with the camera on its side are turned the right way up, and big JPEGs load
much faster. Without it they are loaded by pygame as they are.
"""

import datetime
import json
import os
import random
import re
import threading
import time
import traceback
import pygame
import fonts
import screens as scr
from . import deviantart_library as dl

try:
    from PIL import Image, ImageOps
except ImportError:
    Image = None

PICTURE_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pictures")
PICTURE_SECONDS = 20            # each picture is shown for this long...
FADE_SECONDS = 3                # ...and fades into the next over this long
MAX_ZOOM = dl.MAX_ZOOM          # pictures that would have to be zoomed more than this to fit are low resolution, and skipped
DELETED_FOLDER = "deleted"      # your own pictures, when deleted, are moved to this folder inside PICTURE_FOLDER
NOTICE_SECONDS = 3              # "PICTURE DELETED" is shown for this long
PICTURE_TYPES = (".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp")
FILL_SCREEN = True              # zoom each picture to fill the screen, cutting off what doesn't fit; False: show all of it
WHITE = (255, 255, 255)         # the colour of all the text
BACKGROUND = (0, 0, 0)          # round a picture that isn't the shape of the screen (when FILL_SCREEN is False)
RESCAN_SECONDS = 10             # how often to look in the folder again when it has no pictures
ONLINE_FOLDER = "deviantart"    # the downloaded pictures go in this folder inside PICTURE_FOLDER
OWN_PICTURES = True             # True: show your own pictures too, mixed in with them...
OWN_FOLDER = "my_own"           # ...from this folder inside PICTURE_FOLDER
CREDIT_MARGIN = 20              # the credit's distance from the corner of the screen, in pixels
CREDIT_PAD = 10                 # the space round its text, inside its dark background
CREDIT_BACKGROUND = (0, 0, 0, 150)   # the colour of that background, and how solid it is (0 to 255)
CREDIT_COLOUR = WHITE
CLOCK_MARGIN = 30               # the clock's distance from the top right corner, in pixels
CLOCK_PAD = 20                  # the space round its text, inside its dark background
CLOCK_BACKGROUND = (0, 0, 0, 150)   # as CREDIT_BACKGROUND
CLOCK_TIME_FORMAT = "%H:%M:%S"     # the time, in big text...
CLOCK_DATE_FORMAT = "%d %B %Y"  # ...and under it the date...
CLOCK_DAY_FORMAT = "%A"         # ...and the day of the week (see strftime for what these mean)
CLOCK_DATE_SIZE = fonts.TextSize.LARGE   # the size of the day and the date (the time is XXL)


class LowResolution(Exception):
    """Raised for a picture too small to fill the screen without looking blurred."""


# How much a picture of width x height is zoomed to fill the screen (its edges are then cut
# off), or with FILL_SCREEN False, to be as big as will fit in the screen
def fitScale(width, height):
    fit = max if FILL_SCREEN else min
    return fit(scr.SCREEN_WIDTH / width, scr.SCREEN_HEIGHT / height)


# The size of a picture of width x height once it has been zoomed to fit
def fitSize(width, height):
    scale = fitScale(width, height)
    return max(1, round(width * scale)), max(1, round(height * scale))


# Raise LowResolution if a picture of width x height would have to be zoomed more than MAX_ZOOM
def checkResolution(width, height):
    if fitScale(width, height) > MAX_ZOOM:
        raise LowResolution(f"{width} x {height}")


# A picture as a pygame Surface, scaled to fit the screen, using Pillow
def loadWithPillow(path):
    with Image.open(path) as image:
        width, height = image.size
        if image.getexif().get(0x0112, 1) in (5, 6, 7, 8):     # taken with the camera on its side
            width, height = height, width
        checkResolution(width, height)
        # A JPEG can be decoded at a half, quarter or eighth of its size, which is much
        # quicker. It is never made smaller than the screen.
        image.draft("RGB", (scr.SCREEN_WIDTH, scr.SCREEN_HEIGHT))
        image = ImageOps.exif_transpose(image).convert("RGB")

    image = image.resize(fitSize(*image.size), Image.BICUBIC)
    return pygame.image.fromstring(image.tobytes(), image.size, "RGB")


# A picture as a pygame Surface, scaled to fit the screen, using pygame alone
def loadWithPygame(path):
    image = pygame.image.load(path)
    checkResolution(*image.get_size())
    size = fitSize(*image.get_size())

    # smoothscale only works on 24 and 32 bit pictures
    if image.get_bitsize() >= 24:
        return pygame.transform.smoothscale(image, size)

    return pygame.transform.scale(image, size)


# The whole screen: the picture in the middle of the background
def loadPicture(path):
    if Image is not None:
        picture = loadWithPillow(path)
    else:
        picture = loadWithPygame(path)

    surface = pygame.Surface((scr.SCREEN_WIDTH, scr.SCREEN_HEIGHT))
    surface.fill(BACKGROUND)
    surface.blit(picture, picture.get_rect(center=surface.get_rect().center))
    return surface


# A picture's credit, from the credits.json in its folder, or None if it has none
def pictureCredit(path):
    try:
        with open(os.path.join(os.path.dirname(path), "credits.json"), encoding="utf-8") as file:
            return json.load(file).get(os.path.basename(path))
    except (OSError, ValueError):
        return None


# Draw the credit in the bottom right corner of the surface, on a dark background so that
# it can be read on any picture. It is cut short if it is wider than the screen.
def drawCredit(surface, credit):
    font = fonts.fontFor(fonts.TextSize.SMALL)
    text = credit.upper()
    maxWidth = scr.SCREEN_WIDTH - 2 * (CREDIT_MARGIN + CREDIT_PAD)

    while text and font.size(text)[0] > maxWidth:
        text = text[:-1]

    image = font.render(text.rstrip(), True, CREDIT_COLOUR)
    box = pygame.Surface((image.get_width() + 2 * CREDIT_PAD, image.get_height() + 2 * CREDIT_PAD), pygame.SRCALPHA)
    pygame.draw.rect(box, CREDIT_BACKGROUND, box.get_rect(), border_radius=box.get_height() // 2)
    box.blit(image, (CREDIT_PAD, CREDIT_PAD))
    surface.blit(box, box.get_rect(bottomright=(scr.SCREEN_WIDTH - CREDIT_MARGIN, scr.SCREEN_HEIGHT - CREDIT_MARGIN)))


# How wide text in this format, in this font, can ever be: it is made for every day of
# the week, every month and both halves of the day, with every digit in it changed to
# the widest one, and the widest of those is taken
def widestText(textFormat, font):
    digitWidths = {digit: font.size(digit)[0] for digit in "0123456789"}
    widestDigit = max(digitWidths, key=digitWidths.get)

    widest = 0
    for month in range(1, 13):
        for day in range(1, 8):
            for hour in (0, 12):
                when = datetime.datetime(2026, month, day, hour)
                text = re.sub("[0-9]", widestDigit, when.strftime(textFormat).upper())
                widest = max(widest, font.size(text)[0])
    return widest


# The width of the clock's text, the same whatever the time and date, so that the box
# round it doesn't change size as they change. Worked out the first time it is needed.
_clockTextWidth = None

def clockTextWidth():
    global _clockTextWidth
    if _clockTextWidth is None:
        _clockTextWidth = max(widestText(CLOCK_TIME_FORMAT, fonts.fontFor(fonts.TextSize.XXL)),
                              widestText(CLOCK_DAY_FORMAT, fonts.fontFor(CLOCK_DATE_SIZE)),
                              widestText(CLOCK_DATE_FORMAT, fonts.fontFor(CLOCK_DATE_SIZE)))
    return _clockTextWidth


# Render text with every digit in a space as wide as the widest digit, centred in it,
# so that it stays the same width, and nothing in it moves, as the digits change
def renderFixedDigits(text, font, colour):
    slot = max(font.size(digit)[0] for digit in "0123456789")
    chars = [(char, slot if char.isdigit() else font.size(char)[0]) for char in text]

    image = pygame.Surface((sum(width for _, width in chars), font.get_height()), pygame.SRCALPHA)
    x = 0
    for char, width in chars:
        charImage = font.render(char, True, colour)
        image.blit(charImage, (x + (width - charImage.get_width()) // 2, 0))
        x += width
    return image


# The clock: the time in big text, and the day of the week and the date under it, lined
# up on the right, on a dark background so that they can be read on any picture
def makeClock(now):
    timeText = time.strftime(CLOCK_TIME_FORMAT, now).upper()
    lines = ((time.strftime(CLOCK_DAY_FORMAT, now), CLOCK_DATE_SIZE, WHITE),
             (time.strftime(CLOCK_DATE_FORMAT, now), CLOCK_DATE_SIZE, WHITE))

    images = [renderFixedDigits(timeText, fonts.fontFor(fonts.TextSize.XXL), WHITE)]
    images += [fonts.fontFor(size).render(text.upper(), True, colour) for text, size, colour in lines]
    width = max([clockTextWidth()] + [image.get_width() for image in images]) + 2 * CLOCK_PAD
    height = sum(image.get_height() for image in images) + 2 * CLOCK_PAD

    clock = pygame.Surface((width, height), pygame.SRCALPHA)
    pygame.draw.rect(clock, CLOCK_BACKGROUND, clock.get_rect(), border_radius=CLOCK_PAD * 2)

    y = CLOCK_PAD
    for image in images:
        clock.blit(image, (width - CLOCK_PAD - image.get_width(), y))
        y += image.get_height()

    return clock


class DeviantArtFrameScreen(scr.Screen):

    name = "DEVIANTART"

    def __init__(self, folder=PICTURE_FOLDER):
        self.folder = folder
        self.queue = []             # the pictures still to show this time round
        self.current = None         # the picture being shown (a whole screen)...
        self.previous = None        # ...and the one it is fading in over, or None
        self.shownAt = 0            # when the current one was put up
        self.loading = None         # the thread loading the next picture, or None
        self.loaded = None          # the next picture, once it has been loaded
        self.message = None         # shown instead of the pictures when there are none
        self.lastScan = -RESCAN_SECONDS     # when the folder was last looked in
        self.clock = None           # the clock, drawn again only when what it shows changes...
        self.clockShows = None      # ...which is kept here
        self.currentPath = None     # the file of the picture being shown
        self.notice = None          # "PICTURE DELETED", shown over the pictures...
        self.noticeUntil = 0        # ...until this time


    def start(self):
        if OWN_PICTURES:
            # Made if it isn't there, so that it is clear where your own pictures go
            os.makedirs(self.ownFolder, exist_ok=True)

        dl.start_download_thread(self.onlineFolder)


    @property
    def ownFolder(self):
        return os.path.join(self.folder, OWN_FOLDER)


    @property
    def onlineFolder(self):
        return os.path.join(self.folder, ONLINE_FOLDER)


    # The downloaded pictures, and your own if OWN_PICTURES is True (and the folders inside
    # them), in a random order. Folders starting with "." are skipped (the downloader fills
    # one of those before showing it).
    def findPictures(self):
        paths = []
        folders = [self.onlineFolder] + ([self.ownFolder] if OWN_PICTURES else [])

        for top in folders:
            for folder, subfolders, names in os.walk(top):
                subfolders[:] = [name for name in subfolders if not name.startswith(".")]
                paths += [os.path.join(folder, name) for name in names
                          if os.path.splitext(name)[1].lower() in PICTURE_TYPES]

        random.shuffle(paths)
        return paths


    # Start loading the next picture in the background, as a big photo takes a moment
    # to load and would stop the screen while it did. A picture that won't load is skipped.
    def loadNext(self):
        # The folder isn't looked in more often than every RESCAN_SECONDS, so that an
        # empty one isn't looked in every frame
        if not self.queue and time.time() - self.lastScan >= RESCAN_SECONDS:
            self.queue = self.findPictures()
            self.lastScan = time.time()

        # Pictures that have gone since the folder was looked in (such as the day before's
        # downloads) are passed over
        while self.queue and not os.path.exists(self.queue[-1]):
            self.queue.pop()

        if not self.queue:
            return

        path = self.queue.pop()

        def load():
            try:
                self.loaded = (loadPicture(path), pictureCredit(path), path)
            except LowResolution as exc:
                print(f"Skipping low resolution picture {path} ({exc})")
            except Exception:
                print(f"Can't show picture {path}")
                traceback.print_exc()

        self.loading = threading.Thread(target=load, daemon=True)
        self.loading.start()


    # A message in the middle of the screen, instead of the pictures
    def showMessage(self, text):
        surface = pygame.Surface((scr.SCREEN_WIDTH, scr.SCREEN_HEIGHT))
        surface.fill(BACKGROUND)
        image = fonts.fontFor(fonts.TextSize.LARGE).render(text.upper(), True, WHITE)
        surface.blit(image, image.get_rect(center=surface.get_rect().center))
        self.message = surface


    def enter(self):
        # Start the next picture's time afresh, so it isn't changed as soon as it is shown
        self.shownAt = time.time()


    # Pressing the OK button briefly (or Enter or the space bar on a keyboard) moves on to the
    # next picture. Holding it down (or pressing Delete) deletes the picture being shown.
    def handleEvent(self, event):
        if event.type == scr.OK_HELD or (event.type == pygame.KEYDOWN and event.key == pygame.K_DELETE):
            self.deleteCurrent()
        elif event.type == scr.OK_PRESSED or (event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_SPACE)):
            self.skipCurrent()


    # Move on to the next picture as soon as it has been loaded
    def skipCurrent(self):
        self.shownAt = time.time() - PICTURE_SECONDS


    # Delete the picture being shown, and move on to the next. A downloaded one is deleted
    # (and won't be downloaded again); one of your own is moved to the DELETED_FOLDER instead,
    # in case it was a mistake.
    def deleteCurrent(self):
        path = self.currentPath
        if path is None or not os.path.exists(path):
            return

        try:
            if os.path.commonpath([path, self.onlineFolder]) == self.onlineFolder:
                os.remove(path)
            else:
                deleted = os.path.join(self.folder, DELETED_FOLDER)
                os.makedirs(deleted, exist_ok=True)
                os.replace(path, os.path.join(deleted, os.path.basename(path)))
        except OSError as exc:
            print(f"Can't delete picture {path}: {exc}")
            return

        print(f"Deleted picture {path}")
        self.currentPath = None
        self.shownAt = time.time() - PICTURE_SECONDS     # go on to the next picture now

        font = fonts.fontFor(fonts.TextSize.LARGE)
        image = font.render("PICTURE DELETED", True, WHITE)
        self.notice = pygame.Surface((image.get_width() + 4 * CREDIT_PAD, image.get_height() + 2 * CREDIT_PAD), pygame.SRCALPHA)
        pygame.draw.rect(self.notice, CREDIT_BACKGROUND, self.notice.get_rect(), border_radius=self.notice.get_height() // 2)
        self.notice.blit(image, (2 * CREDIT_PAD, CREDIT_PAD))
        self.noticeUntil = time.time() + NOTICE_SECONDS


    # Only does anything while it is shown. Puts up the next picture once the current
    # one has been shown for long enough and the next one has been loaded.
    def update(self, visible):
        if not visible:
            return

        now = time.time()

        if self.loading is not None and not self.loading.is_alive():
            self.loading = None

        if self.loading is None and self.loaded is None:
            if self.current is None or now - self.shownAt >= PICTURE_SECONDS:
                self.loadNext()

                if self.loading is None and self.current is None and self.message is None:
                    if dl.read_key() is None:
                        self.showMessage(f"No DeviantArt key: put it in {dl.KEY_FILE}")
                    else:
                        self.showMessage("Waiting for pictures from DeviantArt")

        if self.loaded is not None and (self.current is None or now - self.shownAt >= PICTURE_SECONDS):
            # A surface made in another thread is converted here, for faster drawing. The
            # credit is drawn here too, as fonts can only be used on this thread.
            picture, credit, self.currentPath = self.loaded
            self.previous = self.current
            self.current = picture.convert()
            if credit:
                drawCredit(self.current, credit)
            self.loaded = None
            self.message = None
            self.shownAt = now

        if self.previous is not None and now - self.shownAt >= FADE_SECONDS:
            self.previous = None


    def draw(self, surface):
        self.drawPicture(surface)
        self.drawClock(surface)

        if self.notice is not None and time.time() < self.noticeUntil:
            surface.blit(self.notice, self.notice.get_rect(bottomleft=(CREDIT_MARGIN, scr.SCREEN_HEIGHT - CREDIT_MARGIN)))


    def drawPicture(self, surface):
        if self.current is None:
            if self.message is not None:
                surface.blit(self.message, (0, 0))
            else:
                surface.fill(BACKGROUND)
            return

        if self.previous is None:
            surface.blit(self.current, (0, 0))
            return

        fraction = min(1.0, (time.time() - self.shownAt) / FADE_SECONDS)
        surface.blit(self.previous, (0, 0))
        self.current.set_alpha(round(255 * fraction))
        surface.blit(self.current, (0, 0))
        self.current.set_alpha(None)


    # The clock in the top right corner, over the pictures
    def drawClock(self, surface):
        now = time.localtime()
        # Every second, as CLOCK_TIME_FORMAT may show the seconds
        shows = (now.tm_yday, now.tm_hour, now.tm_min, now.tm_sec)

        if shows != self.clockShows:
            self.clock = makeClock(now)
            self.clockShows = shows

        surface.blit(self.clock, self.clock.get_rect(topright=(scr.SCREEN_WIDTH - CLOCK_MARGIN, CLOCK_MARGIN)))
