"""
lcars_sound.py

The beeps for the alerts. They are made from tones when the program starts, so there
are no sound files to look after.

    lcars_sound.initSound()             # once, after pygame.init()
    lcars_sound.play("EMERGENCY")       # or "MILITARY"

If there is no sound device (or the mixer won't start) a warning is printed once and
play() does nothing, so the display carries on without sound.

On the Raspberry Pi the sound goes to wherever it is set to in the desktop's sound
settings (HDMI, the headphone socket, a USB speaker...), and its loudness is set by
VOLUME below and by the system volume.
"""

import array
import math

import pygame

SAMPLE_RATE = 44100
VOLUME = 0.9                # 0 to 1
FADE_SECONDS = 0.008        # each note fades in and out over this long, which stops the clicks

# A sound is a list of notes: (frequency in Hz, seconds), where a frequency of 0 is a pause.
SOUNDS = {
    # An urgent two-tone warble, three times
    "EMERGENCY": ((880, 0.16), (0, 0.04), (660, 0.16), (0, 0.04)) * 3,

    # Two short rising chirps
    "MILITARY": ((660, 0.08), (0, 0.04), (990, 0.08), (0, 0.10), (660, 0.08), (0, 0.04), (990, 0.08)),
}

sounds = {}                 # name -> pygame.mixer.Sound, filled in by initSound
muted = False               # True: play() does nothing (the LCARS screen's sound is turned off)


# The samples of one note, as numbers from -32767 to 32767. A pause is all zeros.
def noteSamples(frequency, seconds):
    count = round(SAMPLE_RATE * seconds)
    fade = max(1, round(SAMPLE_RATE * FADE_SECONDS))
    samples = []

    for i in range(count):
        if frequency == 0:
            samples.append(0)
            continue

        envelope = min(1.0, i / fade, (count - 1 - i) / fade)
        value = math.sin(2 * math.pi * frequency * i / SAMPLE_RATE)
        samples.append(round(32767 * VOLUME * envelope * value))

    return samples


# A pygame Sound of the notes, which are (frequency, seconds) pairs. The mixer is set up
# for two channels, so each sample is given to both of them.
def makeSound(notes):
    samples = []
    for frequency, seconds in notes:
        samples.extend(noteSamples(frequency, seconds))

    stereo = array.array("h")
    for sample in samples:
        stereo.append(sample)
        stereo.append(sample)

    return pygame.mixer.Sound(buffer=stereo.tobytes())


# Start the mixer and make the sounds. Returns True if there is sound.
def initSound():
    sounds.clear()

    try:
        pygame.mixer.quit()
        pygame.mixer.init(frequency=SAMPLE_RATE, size=-16, channels=2)

        for name, notes in SOUNDS.items():
            sounds[name] = makeSound(notes)

    except pygame.error as exc:
        print(f"No sound for the alerts: {exc}")
        sounds.clear()
        return False

    return True


# Play a sound by name (see SOUNDS). It plays in the background, and a sound that is
# already playing is not cut off. Does nothing if there is no sound.
def play(name):
    sound = sounds.get(name)

    if sound is not None and not muted:
        sound.play()
		
		