"""
screens.py

The display shows one screen at a time (the LCARS screen, the picture frame...). The NEXT
button (or the right arrow key) moves on to the next, going round them all, and the SOUND
button (or the left arrow key, or M) sets the volume of the one shown: low, medium, high or
off, in turn, with a notice in the middle of the screen saying which (see gpio_buttons.py).
A screen can have levels of its own (volumes and volumeOrder), as the clock does. Holding the
SOUND button down (or the C key) is passed on to the screen shown, as SOUND_HELD.

To add a screen, make a folder for it (like lcars_frame and deviantart_frame) with an empty
__init__.py and a file with a class based on Screen in it, fill in the methods it needs,
and add one of it to the list in main() in lcars.py. Nothing else has to change. Inside
the folder, its files import each other with "from . import ...".

    class MyScreen(screens.Screen):
        name = "MINE"

        def update(self, visible):
            ...                         # every frame, whether it is shown or not

        def draw(self, surface):
            ...                         # draw the whole screen on the surface
"""

import os
import pygame

# Its settings are in settings.py (next to lcars.py)
from settings import (
    SCREEN_WIDTH,
    SCREEN_HEIGHT,
    SCREEN_NOTICE_SECONDS as NOTICE_SECONDS,
    SCREEN_VOLUMES as VOLUMES,
    SCREEN_VOLUME_ORDER as VOLUME_ORDER,
)

# Posted (e.g. by the buttons, from their own thread) to move to the next screen, or to turn
# the sound of the one shown off or on
NEXT_SCREEN = pygame.event.custom_type()
TOGGLE_SOUND = pygame.event.custom_type()

# Posted when the OK button has been pressed briefly, or held down for a while, or when the
# SOUND button has been held down (see gpio_buttons.py). They are passed on to the screen
# that is shown, which can do what it likes with them.
OK_PRESSED = pygame.event.custom_type()
OK_HELD = pygame.event.custom_type()
SOUND_HELD = pygame.event.custom_type()


class Screen:

    name = "SCREEN"             # shown in the messages when the screen is changed
    hasSound = False            # True for a screen that makes any sound...
    volumes = VOLUMES           # ...the levels the SOUND button goes round: (name, how loud)...
    volumeOrder = VOLUME_ORDER  # ...in this order...
    volumeLevel = 3             # ...and the one it is at, as an index into volumes (it starts high)

    @property
    def volume(self):
        return self.volumes[self.volumeLevel][1]

    @property
    def soundOn(self):
        return self.volume > 0

    # Once, when the program starts, after the display has been set up: load things, start threads
    def start(self):
        pass

    # Once, when the program ends
    def stop(self):
        pass

    # When the screen is about to be shown...
    def enter(self):
        pass

    # ...and when another one is about to be shown instead
    def leave(self):
        pass

    # A pygame event that wasn't used to change the screen or to quit. Only the screen
    # that is shown gets them.
    def handleEvent(self, event):
        pass

    # Every frame, for every screen. visible is True for the one that is shown: the others
    # can carry on with their work in the background, or do nothing until they are shown.
    def update(self, visible):
        pass

    # Every frame, for the screen that is shown: draw all of it on the surface
    def draw(self, surface):
        raise NotImplementedError

    # The screen's sounds, as (pygame Sound, how loud it is compared with the others), so
    # that the SOUND button can set their volume
    def soundList(self):
        return []

    # Set the volume (an index into volumes), with the SOUND button
    def setVolumeLevel(self, level):
        wasOn = self.soundOn
        self.volumeLevel = level
        for sound, loudness in self.soundList():
            if sound is not None:
                sound.set_volume(min(1.0, self.volume * loudness))
        if self.soundOn != wasOn:
            self.setSound(self.soundOn)

    # The words of the notice when the SOUND button sets the volume to `level`
    def volumeNotice(self, level):
        return f"{self.name}   SOUND OFF" if level == 0 else f"{self.name}   VOLUME {self.volumes[level][0]}"

    # Called when the sound is turned off or back on: a screen stops anything that keeps
    # playing (a loop, say) here. While it is off, a screen plays nothing (see soundOn).
    def setSound(self, on):
        pass


# Keeps the screens, and which one is shown
class ScreenSwitcher:

    def __init__(self, screens):
        self.screens = list(screens)
        self.index = 0
        self.notice = None          # (picture, when it was shown) of the sound notice

    @property
    def current(self):
        return self.screens[self.index]

    def start(self):
        for screen in self.screens:
            screen.start()

        self.current.enter()

    def stop(self):
        for screen in self.screens:
            screen.stop()

    # Show the screen this many along (1 = next, -1 = previous), going round at the ends
    def move(self, step):
        if len(self.screens) < 2:
            return

        self.current.leave()
        self.index = (self.index + step) % len(self.screens)
        print(f"Screen: {self.current.name}")
        self.current.enter()

    # Change screen, or turn its sound off or on, if it is one of the events that does that;
    # otherwise pass it on to the screen that is shown
    def handleEvent(self, event):
        if event.type == NEXT_SCREEN or (event.type == pygame.KEYDOWN and event.key == pygame.K_RIGHT):
            self.notice = None
            self.move(1)
        elif event.type == TOGGLE_SOUND or (event.type == pygame.KEYDOWN and event.key in (pygame.K_LEFT, pygame.K_m)):
            self.toggleSound()
        else:
            self.current.handleEvent(event)

    # The next volume for the screen shown, and a notice saying what it is
    def toggleSound(self):
        screen = self.current
        if screen.hasSound:
            order = screen.volumeOrder
            level = order[(order.index(screen.volumeLevel) + 1) % len(order)]
            screen.setVolumeLevel(level)
            text = screen.volumeNotice(level)
            print(f"Sound: {text}")
            colour = (255, 153, 0) if screen.soundOn else (230, 61, 61)
            bars, total = level, len(screen.volumes) - 1
        else:
            text, colour, bars, total = f"{screen.name}   NO SOUND", (153, 153, 204), None, 0
        self.notice = (makeNotice(text, colour, bars, total), pygame.time.get_ticks())

    def update(self):
        for screen in self.screens:
            screen.update(screen is self.current)

    def draw(self, surface):
        self.current.draw(surface)

        if self.notice:
            picture, shown = self.notice
            age = (pygame.time.get_ticks() - shown) / 1000
            if age > NOTICE_SECONDS:
                self.notice = None
            else:
                picture.set_alpha(int(255 * min(1.0, (NOTICE_SECONDS - age) / 0.4)))
                surface.blit(picture, picture.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)))


# The notice of the volume: an LCARS lozenge with the words in it, and beside them, for a
# screen with sound, a bar for each level above off showing how loud (bars of them lit, out
# of total). It is used for other notices too (the clock's), without the bars.
def makeNotice(text, colour, bars=None, total=3):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts", "Antonio-Bold.ttf")
    try:
        font = pygame.font.Font(path, 64)
    except (pygame.error, OSError):
        font = pygame.font.SysFont("arial", 64, bold=True)
    words = font.render(text, True, (0, 0, 0))
    h = words.get_height() + 30
    barsWidth = 0 if bars is None else total * 26 + 40
    w = words.get_width() + 2 * h + barsWidth
    picture = pygame.Surface((w, h), pygame.SRCALPHA)
    picture.fill((0, 0, 0, 0))
    pygame.draw.rect(picture, colour, picture.get_rect(), border_radius=h // 2)
    picture.blit(words, words.get_rect(midleft=(h, h // 2)))
    if bars is not None:
        x = h + words.get_width() + 40
        for i in range(total):
            height = int(h * (0.3 + 0.54 * i / max(1, total - 1)))
            rect = pygame.Rect(x + i * 26, h - 16 - height, 18, height)
            if i < bars:
                pygame.draw.rect(picture, (0, 0, 0), rect)
            else:
                pygame.draw.rect(picture, (0, 0, 0), rect, 2)
    return picture
