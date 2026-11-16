"""
gpio_buttons.py

Two push buttons on the Raspberry Pi's GPIO pins (and two more, if you like). Each one is
wired between its pin and a ground (GND) pin: the Pi's own pull-up resistor holds the pin high,
and pressing the button pulls it low. No resistors are needed.

    SOUND_PIN     GPIO22  (physical pin 15)   button 1. Pressed briefly: the volume of the screen
                                              shown (on the clock, of the ticks: low, medium,
                                              high, max, off). Held down for HOLD_SECONDS:
                                              passed on to the screen shown (the clock turns its
                                              chimes on or off)
    NEXT_PIN      GPIO17  (physical pin 11)   button 2. Pressed briefly: the next screen, going
                                              round them all (each clock face is one). Held down:
                                              passed on to the screen shown as OK_PRESSED (the
                                              next picture in the frame, the clock's chime, the
                                              fish fed, a warp jump...)
    OK_PIN        GPIO27  (physical pin 13)   optional (None if there isn't one): pressed briefly
                                              or held down, passed on to the screen shown (held,
                                              the DeviantArt frame deletes the picture shown)
    TIME_PIN      GPIO23  (physical pin 16)   optional: pressed briefly, the city clock shows the
                                              city an hour later; held down, back to now
    ground        GND     (physical pin 9, 14 or 20)

Each button can be pressed briefly or held down, so it posts its event when it is let go:
screens.TOGGLE_SOUND (as the left arrow key does), screens.NEXT_SCREEN (as the right arrow
key does) or screens.OK_PRESSED. Holding one down posts its held event at once (SOUND_HELD,
OK_PRESSED for button 2, OK_HELD or TIME_HELD), and nothing more when it is let go.

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
    BUTTONS_TIME_PIN as TIME_PIN,
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
    pins = [(SOUND_PIN, scr.TOGGLE_SOUND, scr.SOUND_HELD),
            (NEXT_PIN, scr.NEXT_SCREEN, scr.OK_PRESSED)]
    if OK_PIN is not None:
        pins.append((OK_PIN, scr.OK_PRESSED, scr.OK_HELD))
    if TIME_PIN is not None:
        pins.append((TIME_PIN, scr.TIME_PRESSED, scr.TIME_HELD))
    for pin, eventType, heldType in pins:
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
