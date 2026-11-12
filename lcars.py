# lcars2.py
#
# Starts the display: a set of screens, one shown at a time (see screens.py).
#
#   lcars_frame/      the LCARS screen, and everything it uses
#   deviantart_frame/ the DeviantArt picture frame, its daily downloads and its pictures
#   biomonitor_frame/ the sickbay biomonitor dials
#   fonts.py          the fonts every screen draws its text in (the font files are in fonts/)
#
#   LEFT and RIGHT arrow keys, or the two GPIO buttons (see gpio_buttons.py), to change screen.
#   ESC or Q to quit.

import pygame
import fonts
import gpio_buttons as gb
import screens as scr
from lcars_frame.lcars_screen import LcarsScreen
from deviantart_frame.deviantart_frame import DeviantArtFrameScreen
from biomonitor_frame.biomonitor import BiomonitorScreen


FRAME_RATE = 30


def main():
    pygame.init()
    pygame.mouse.set_visible(False)
    fonts.initFonts()
    clock = pygame.time.Clock()
    screen = pygame.display.set_mode((scr.SCREEN_WIDTH, scr.SCREEN_HEIGHT))

    # The screens, in the order the right arrow key (or the next button) goes through them.
    # The first is shown at the start. To add a screen, see screens.py.
    switcher = scr.ScreenSwitcher([
        LcarsScreen(),
        DeviantArtFrameScreen(),
        BiomonitorScreen(),
    ])
    switcher.start()
    buttons = gb.startButtons()

    running = True

    while running:

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                print("Quit")
                running = False

            elif event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_q):
                print("Escape")
                running = False

            else:
                switcher.handleEvent(event)

        switcher.update()
        switcher.draw(screen)
        pygame.display.flip()

        clock.tick(FRAME_RATE)


    gb.stopButtons(buttons)
    switcher.stop()
    pygame.quit()


if __name__ == "__main__":

    main()
