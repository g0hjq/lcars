"""
gpio_buttons.py

Three push buttons on the Raspberry Pi's GPIO pins. Each one is wired between its pin and
a ground (GND) pin: the Pi's own pull-up resistor holds the pin high, and pressing the
button pulls it low. No resistors are needed.

    PREVIOUS_PIN  GPIO22  (physical pin 15)   previous screen
    NEXT_PIN      GPIO17  (physical pin 11)   next screen
    OK_PIN        GPIO27  (physical pin 13)   pressed briefly, or held down for HOLD_SECONDS:
                                              passed on to the screen shown (the DeviantArt
                                              frame moves on to the next picture, or deletes
                                              the one it is showing)
    ground        GND     (physical pin 9, 14 or 20)

A press of the first two posts screens.PREVIOUS_SCREEN or screens.NEXT_SCREEN, which the
main loop handles just like the left and right arrow keys. Pressing the OK one
briefly posts screens.OK_PRESSED when it is let go; holding it down posts screens.OK_HELD
(and nothing more when it is let go).

Uses gpiozero, which is already on Raspberry Pi OS (on a Pi 5 it works through lgpio:
sudo apt install python3-gpiozero python3-lgpio if it isn't). On a PC, or if the
pins can't be had, a message is printed and the keys still work.
"""

import pygame
import screens as scr

PREVIOUS_PIN = 22
NEXT_PIN = 17
OK_PIN = 27
HOLD_SECONDS = 2            # how long the OK button must be held down
BOUNCE_SECONDS = 0.10       # a press within this long of the last is taken as contact bounce

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


# Make the OK button post OK_HELD once it has been held down for HOLD_SECONDS, or
# OK_PRESSED when it is let go if it wasn't held that long
def setUpOkButton(button):
    state = {"held": False}

    def pressed():
        state["held"] = False

    def held():
        state["held"] = True
        pygame.event.post(pygame.event.Event(scr.OK_HELD))

    def released():
        if not state["held"]:
            pygame.event.post(pygame.event.Event(scr.OK_PRESSED))
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

    for pin, eventType in ((PREVIOUS_PIN, scr.PREVIOUS_SCREEN),
                           (NEXT_PIN, scr.NEXT_SCREEN),
                           (OK_PIN, None)):
        try:
            button = Button(pin, pull_up=True, bounce_time=BOUNCE_SECONDS, hold_time=HOLD_SECONDS)
        except Exception as exc:
            print(f"No button on GPIO{pin}: {exc}")
            continue

        # gpiozero calls when_held once per hold (hold_repeat is off)
        if eventType is None:
            setUpOkButton(button)
        else:
            button.when_pressed = poster(eventType)
        buttons.append(button)

    return buttons


def stopButtons(buttons):
    for button in buttons:
        button.close()
