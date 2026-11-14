# fonts.py
#
# The fonts every screen draws its text in, one for each TextSize.
#
#   fonts.initFonts()                                   # once, after pygame.init()
#   image = fonts.fontFor(fonts.TextSize.LARGE).render("HELLO", True, (255, 255, 255))
#
# The text is drawn in Antonio, a free font in the LCARS style (its licence is fonts/OFL.txt),
# from the two files in the fonts folder next to this script. If they aren't there,
# FONT_NAME is used instead.

import os
import pygame
from enum import Enum

FONT_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
# Its settings are in settings.py (next to lcars.py)
from settings import (
    FONT_FILE,
    FONT_FILE_BOLD,
    FONT_FILE_SCALE,
    FONT_NAME,
    FONT_SIZE_XS,
    FONT_SIZE_SMALL,
    FONT_SIZE_LIST,
    FONT_SIZE_MEDIUM,
    FONT_SIZE_LARGE,
    FONT_SIZE_XL,
    FONT_SIZE_XXL,
)


class TextSize(Enum):
    XS = 301
    SMALL = 302
    LIST = 307
    MEDIUM = 303
    LARGE = 304
    XL = 305
    XXL = 306


loadedFonts = {}    # text size -> its font, filled in by initFonts
capMetrics = {}     # text size -> (top, height) of a capital letter in that font's pictures of text


# Call this once, after pygame.init() and before drawing any text.
def initFonts():

    # Say so, once, if the font isn't there, as otherwise the only sign is the wrong look
    for fileName in (FONT_FILE, FONT_FILE_BOLD):
        path = os.path.join(FONT_FOLDER, fileName)
        if not os.path.exists(path):
            print(f"Font file not found: {path} - using {FONT_NAME} instead")

    loadedFonts.clear()
    loadedFonts.update({
        TextSize.XS:     loadFont(FONT_SIZE_XS, False),
        TextSize.SMALL:  loadFont(FONT_SIZE_SMALL, False),
        TextSize.LIST:   loadFont(FONT_SIZE_LIST, False),
        TextSize.MEDIUM: loadFont(FONT_SIZE_MEDIUM, True),
        TextSize.LARGE:  loadFont(FONT_SIZE_LARGE, True),
        TextSize.XL:     loadFont(FONT_SIZE_XL, True),
        TextSize.XXL:    loadFont(FONT_SIZE_XXL, True),
    })

    capMetrics.clear()


# A font of this size, from the Antonio files if they are there, otherwise the system font
def loadFont(size, bold):
    path = os.path.join(FONT_FOLDER, FONT_FILE_BOLD if bold else FONT_FILE)

    if os.path.exists(path):
        try:
            return pygame.font.Font(path, round(size * FONT_FILE_SCALE))
        except (pygame.error, OSError) as exc:
            print(f"Could not load the font {path}: {exc} - using {FONT_NAME} instead")

    return pygame.font.SysFont(FONT_NAME, size, bold=bold)


def fontFor(textSize):
    return loadedFonts[textSize]


# Where a capital letter sits inside a picture of text in this size: how far down its top
# is, and how tall it is. A font's pictures have different amounts of space above and below
# the letters, so this is what text is centred on to look centred in its box.
def capMetricsFor(textSize):
    if textSize not in capMetrics:
        ink = fontFor(textSize).render("H", True, (255, 255, 255)).get_bounding_rect()
        capMetrics[textSize] = (ink.top, ink.height)

    return capMetrics[textSize]
