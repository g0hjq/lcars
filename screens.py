"""
screens.py

The display shows one screen at a time (the LCARS screen, the picture frame...), and
the left and right arrow keys, or the two buttons (see gpio_buttons.py), move between them.

To add a screen, make a folder for it (like lcars_frame and deviantart_frame) with an empty
__init__.py and a file with a class based on Screen in it, fill in the methods it needs,
and add one of it to the list in main() in lcars2.py. Nothing else has to change. Inside
the folder, its files import each other with "from . import ...".

    class MyScreen(screens.Screen):
        name = "MINE"

        def update(self, visible):
            ...                         # every frame, whether it is shown or not

        def draw(self, surface):
            ...                         # draw the whole screen on the surface
"""

import pygame

# The size of the display, which every screen fills
SCREEN_WIDTH = 1920
SCREEN_HEIGHT = 1080

# Posted (e.g. by the buttons, from their own thread) to move to the next or previous screen
NEXT_SCREEN = pygame.event.custom_type()
PREVIOUS_SCREEN = pygame.event.custom_type()

# Posted when the OK button has been pressed briefly, or held down for a while (see
# gpio_buttons.py). They are passed on to the screen that is shown, which can do what it
# likes with them.
OK_PRESSED = pygame.event.custom_type()
OK_HELD = pygame.event.custom_type()


class Screen:

    name = "SCREEN"             # shown in the messages when the screen is changed

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


# Keeps the screens, and which one is shown
class ScreenSwitcher:

    def __init__(self, screens):
        self.screens = list(screens)
        self.index = 0

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

    # Change screen if it is one of the events that does that, otherwise pass it on to
    # the screen that is shown
    def handleEvent(self, event):
        if event.type == NEXT_SCREEN or (event.type == pygame.KEYDOWN and event.key == pygame.K_RIGHT):
            self.move(1)
        elif event.type == PREVIOUS_SCREEN or (event.type == pygame.KEYDOWN and event.key == pygame.K_LEFT):
            self.move(-1)
        else:
            self.current.handleEvent(event)

    def update(self):
        for screen in self.screens:
            screen.update(screen is self.current)

    def draw(self, surface):
        self.current.draw(surface)
