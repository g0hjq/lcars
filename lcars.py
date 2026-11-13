# lcars2.py
#
# Starts the display: a set of screens, one shown at a time (see screens.py).
#
#   lcars_frame/      the LCARS screen, and everything it uses
#   deviantart_frame/ the DeviantArt picture frame, its daily downloads and its pictures
#   biomonitor_frame/ the sickbay biomonitor dials
#   clock_frame/      an old analogue clock, with the date, that chimes the quarters
#   departures_frame/ a split-flap board of the aircraft overhead
#   aquarium_frame/   a fish tank
#   viewscreen_frame/ the view from the bridge, with warp jumps to new planets
#   lavalamp_frame/   a lava lamp
#   synth.py          makes the sounds the screens play from tones and noise
#   fonts.py          the fonts every screen draws its text in (the font files are in fonts/)
#
#   RIGHT arrow key, or the NEXT button, for the next screen; LEFT arrow key (or M), or the
#   SOUND button, to set the volume of the screen shown: low, medium, high or off (see gpio_buttons.py).
#   ESC or Q to quit.

import pygame
import fonts
import gpio_buttons as gb
import screens as scr
from lcars_frame.lcars_screen import LcarsScreen
from deviantart_frame.deviantart_frame import DeviantArtFrameScreen
from biomonitor_frame.biomonitor import BiomonitorScreen
from clock_frame.clock import ClockScreen
from departures_frame.departures import DeparturesScreen
from aquarium_frame.aquarium import AquariumScreen
from viewscreen_frame.viewscreen import ViewscreenScreen
from lavalamp_frame.lavalamp import LavaLampScreen


FRAME_RATE = 30


def main():
    pygame.init()
    pygame.mouse.set_visible(False)
    fonts.initFonts()
    clock = pygame.time.Clock()
    screen = pygame.display.set_mode((scr.SCREEN_WIDTH, scr.SCREEN_HEIGHT))

    # The screens, in the order the right arrow key (or the next button) goes through them.
    # The first is shown at the start. To add a screen, see screens.py.
    # The departures board shows the aircraft the LCARS screen fetches.
    lcars = LcarsScreen()
    switcher = scr.ScreenSwitcher([
        lcars,
        DeparturesScreen(lcars),
        DeviantArtFrameScreen(),
        BiomonitorScreen(),
        ClockScreen(),
        AquariumScreen(),
        ViewscreenScreen(),
        LavaLampScreen(),
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
