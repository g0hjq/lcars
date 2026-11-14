"""
gpio_buttons.py

Three push buttons on the Raspberry Pi's GPIO pins. Each one is wired between its pin and
a ground (GND) pin: the Pi's own pull-up resistor holds the pin high, and pressing the
button pulls it low. No resistors are needed.

    SOUND_PIN     GPIO22  (physical pin 15)   the volume of the screen shown: low, medium, high, off;
                                              held down for HOLD_SECONDS, passed on to the screen
                                              shown (the clock turns its chimes on or off)
    NEXT_PIN      GPIO17  (physical pin 11)   next screen, going round them all
    OK_PIN        GPIO27  (physical pin 13)   pressed briefly, or held down for HOLD_SECONDS:
                                              passed on to the screen shown (the DeviantArt
                                              frame moves on to the next picture, or deletes
                                              the one it is showing)
    ground        GND     (physical pin 9, 14 or 20)

A press of the NEXT button posts screens.NEXT_SCREEN, which the main loop handles just
like the right arrow key. The SOUND and OK buttons can be pressed briefly or held down, so
they post their event when they are let go: screens.TOGGLE_SOUND (as the left arrow key
does) or screens.OK_PRESSED. Holding one down posts screens.SOUND_HELD or screens.OK_HELD
(and nothing more when it is let go).

Uses gpiozero, which is already on Raspberry Pi OS (on a Pi 5 it works through lgpio:
sudo apt install python3-gpiozero python3-lgpio if it isn't). On a PC, or if the
pins can't be had, a message is printed and the keys still work.
"""

import pygame
import screens as scr

# Its settings are in settings.py (next to lcars.py)
from settings import (
    BUTTONS_SOUND_PIN as SOUND_PIN,
    BUTTONS_NEXT_PIN as NEXT_PIN,
    BUTTONS_OK_PIN as OK_PIN,
    BUTTONS_HOLD_SECONDS as HOLD_SECONDS,
    BUTTONS_BOUNCE_SECONDS as BOUNCE_SECONDS,
)

try:
    from gpiozero import Button
except ImportError:
    Button = None


# A function that posts this event, for a button to call when it is pressed (from
# gpiozero's thread: posting an event is safe from any thread)
def poster(eventType):
    def post():
        pygame.event.post(pygame.event.Event(eventType))

    return post


# Make a button post heldEvent once it has been held down for HOLD_SECONDS, or
# pressedEvent when it is let go if it wasn't held that long
def setUpHoldButton(button, pressedEvent, heldEvent):
    state = {"held": False}

    def pressed():
        state["held"] = False

    def held():
        state["held"] = True
        pygame.event.post(pygame.event.Event(heldEvent))

    def released():
        if not state["held"]:
            pygame.event.post(pygame.event.Event(pressedEvent))
        state["held"] = False

    button.when_pressed = pressed
    button.when_held = held
    button.when_released = released


# Set up the buttons. Returns them, as they stop working once they are thrown away,
# so the caller must keep them (and can close them at the end with stopButtons).
def startButtons():
    if Button is None:
        print("No gpiozero, so no GPIO buttons: use the arrow keys")
        return []

    buttons = []

    # (pin, the event when pressed, and the event when held down: None if it can't be held)
    for pin, eventType, heldType in ((SOUND_PIN, scr.TOGGLE_SOUND, scr.SOUND_HELD),
                                     (NEXT_PIN, scr.NEXT_SCREEN, None),
                                     (OK_PIN, scr.OK_PRESSED, scr.OK_HELD)):
        try:
            button = Button(pin, pull_up=True, bounce_time=BOUNCE_SECONDS, hold_time=HOLD_SECONDS)
        except Exception as exc:
            print(f"No button on GPIO{pin}: {exc}")
            continue

        # gpiozero calls when_held once per hold (hold_repeat is off)
        if heldType is not None:
            setUpHoldButton(button, eventType, heldType)
        else:
            button.when_pressed = poster(eventType)
        buttons.append(button)

    return buttons


def stopButtons(buttons):
    for button in buttons:
        button.close()
