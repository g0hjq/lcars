"""
synth.py

Turns sounds made with numpy into pygame Sounds, so that screens can make their sounds
from tones and noise when the program starts, rather than needing sound files.

    import synth
    t = synth.times(0.5)                                    # the times of half a second of samples
    beep = synth.makeSound(np.sin(2 * np.pi * 440 * t) * np.exp(-t / 0.1), volume=0.5)
    if beep:
        beep.play()

The samples are floats, in a 1-D array (the same on both sides) or an (n, 2) one (left,
right). They are scaled so that the loudest is at volume (0 to 1). If there is no sound
device, makeSound returns None, so check before playing.
"""

import numpy as np
import pygame

SAMPLE_RATE = 44100


# Start the mixer if nothing has yet, as the LCARS screen sets it up (see lcars_sound.py).
# True if there is sound, in the format these sounds are made in.
def ready():
    try:
        if not pygame.mixer.get_init():
            pygame.mixer.init(frequency=SAMPLE_RATE, size=-16, channels=2)
    except pygame.error as exc:
        print(f"No sound: {exc}")
        return False

    return pygame.mixer.get_init()[:2] == (SAMPLE_RATE, -16)


# The time of each sample over this many seconds
def times(seconds):
    return np.arange(int(SAMPLE_RATE * seconds)) / SAMPLE_RATE


# White noise of this many seconds, from -1 to 1
def noise(seconds, rng=None):
    rng = rng or np.random.default_rng()
    return rng.uniform(-1, 1, int(SAMPLE_RATE * seconds))


# A simple low-pass filter: smooths the samples over about `samples` of them
def smooth(samples, width):
    width = max(1, int(width))
    return np.convolve(samples, np.ones(width) / width, "same")


# A pygame Sound of the samples, or None if there is no sound
def makeSound(samples, volume=1.0):
    if not ready():
        return None

    samples = np.asarray(samples, dtype=np.float64)
    if samples.ndim == 1:
        samples = np.column_stack((samples, samples))

    peak = np.max(np.abs(samples))
    if peak > 0:
        samples = samples / peak

    # fade the very end, so that it never stops with a click
    fade = min(len(samples), int(SAMPLE_RATE * 0.005))
    if fade:
        samples[-fade:] *= np.linspace(1, 0, fade)[:, None]

    pcm = (samples * 32767 * volume).astype(np.int16)
    if pygame.mixer.get_init()[2] == 1:
        pcm = pcm.mean(axis=1).astype(np.int16)

    try:
        return pygame.mixer.Sound(buffer=np.ascontiguousarray(pcm).tobytes())
    except pygame.error as exc:
        print(f"Could not make a sound: {exc}")
        return None


# Add one sound into another (both arrays of samples), starting at `at` seconds, cutting
# off whatever would go past the end
def mixIn(into, sound, at):
    start = int(at * SAMPLE_RATE)
    if start >= len(into):
        return
    end = min(len(into), start + len(sound))
    into[start:end] += sound[:end - start]
