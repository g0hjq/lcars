"""
clock.py

A screen with a big clock on it, in one of five faces, changed with the OK button (or Enter):

  BRASS      an old brass clock with Roman numerals, a moon dial and a calendar, which
             chimes the Westminster Quarters and strikes the hour (brass.py)
  RAILWAY    a station clock whose red seconds hand sweeps round in 58.5 seconds and waits
             at the top for the minute hand to jump; a station chime on the hour (railway.py)
  DECO       an Art Deco mantel clock in black lacquer and chrome, with a ding-dong chime at
             the quarters and a gong for the hour (deco.py)
  NIXIE      six glowing Nixie tubes, with the time pips before each hour (nixie.py)
  FLIP       a 1970s flip clock, whose cards fall over with a clack (flip.py)

Each face has its own sounds, which are made when the program starts, so there are no sound
files. Chimes are heard even behind the other screens (if CHIME_WHEN_HIDDEN); ticks only while
the clock is shown. The SOUND button sets only how loud the ticks are, going round
TICK_VOLUMES (LOWER, LOW, MEDIUM, HIGH and OFF): the chimes are always as loud as
CHIME_VOLUME. Holding SOUND down (or C) turns the chimes off, or back on. Holding OK down (or
Delete) plays the face's last chime again, like the repeat on an old clock. Between
QUIET_FROM and QUIET_UNTIL it neither ticks nor chimes.

All the settings, for the screen and for each face, are in settings.py (next to lcars.py).

Each face is drawn the first time it is shown, which takes a moment, and kept.

Uses numpy (on Raspberry Pi OS already; otherwise sudo apt install python3-numpy).
"""

import datetime
import math
import threading
import time
import pygame
import screens as scr
from .common import sysFont
from .brass import BrassFace
from .railway import RailwayFace
from .deco import DecoFace
from .nixie import NixieFace
from .flip import FlipFace

##==================================================================
## SETTINGS (they are in settings.py, next to lcars.py)
##==================================================================

from settings import (
    CLOCK_FACES as FACES,
    CLOCK_CHIME as CHIME,
    CLOCK_TICK as TICK,
    CLOCK_CHIME_WHEN_HIDDEN as CHIME_WHEN_HIDDEN,
    CLOCK_CHIME_VOLUME as CHIME_VOLUME,
    CLOCK_TICK_LOUDNESS as TICK_LOUDNESS,
    CLOCK_TICK_VOLUMES as TICK_VOLUMES,
    CLOCK_TICK_VOLUME_ORDER as TICK_VOLUME_ORDER,
    CLOCK_QUIET_FROM as QUIET_FROM,
    CLOCK_QUIET_UNTIL as QUIET_UNTIL,
    CLOCK_STATUS_CORNER as STATUS_CORNER,
    CLOCK_NOTICE_SECONDS as NOTICE_SECONDS,
    CLOCK_NOTICE_COLOUR as NOTICE_COLOUR,
)

# The faces, by name
FACE_CLASSES = {face.name: face for face in (BrassFace, RailwayFace, DecoFace, NixieFace, FlipFace)}


class ClockScreen(scr.Screen):

    name = "CLOCK"
    hasSound = True
    volumes = TICK_VOLUMES              # the SOUND button sets the ticks' volume, at these levels...
    volumeOrder = TICK_VOLUME_ORDER
    volumeLevel = len(TICK_VOLUMES) - 1     # ...starting at the loudest

    def start(self):
        self.faces = [FACE_CLASSES[name.upper()]() for name in FACES]
        self.built = set()              # the faces drawn so far
        self.index = 0
        self.build(self.face)

        self.visible = False
        self.chimesOn = CHIME           # holding the SOUND button turns them off, or back on
        self.lastSecond = None          # the second whose sounds have been started
        self.due = []                   # (pygame ticks, Sound) still to be played: the strokes of the hour, say
        self.playing = []               # the sounds started, so that they can be stopped
        self.status = None              # the words in the corner, and their picture
        self.statusImage = None
        self.notice = None              # (picture, when) of the face's name in the middle...
        self.noticeShown = False        # ...and whether it has been drawn yet
        self.lastFace = self.face       # the face before, shown while a new one is being drawn

        self.stopping = threading.Event()
        threading.Thread(target=self.tickLoop, name="clock ticks", daemon=True).start()


    @property
    def face(self):
        return self.faces[self.index]


    # Draw a face and make its sounds, the first time it is needed
    def build(self, face):
        if face in self.built:
            return
        started = pygame.time.get_ticks()
        face.build(CHIME_VOLUME, CHIME_VOLUME * TICK_LOUDNESS)
        self.built.add(face)
        ticks = face.tickSounds()
        for sound in face.sounds():
            if sound is not None:
                sound.set_volume(min(1.0, self.volume) if sound in ticks else 1.0)
        face.enter()
        face.update(datetime.datetime.now())
        print(f"Clock: {face.name} drawn in {(pygame.time.get_ticks() - started) / 1000:.1f}s")


    def stop(self):
        self.stopping.set()


    # The ticks, played by a thread of their own at the very moment each is due, as the frames
    # are too far apart (a thirtieth of a second) to keep them evenly spaced. It works out the
    # next beat from the clock, as the hands do, so they keep in step.
    def tickLoop(self):
        while not self.stopping.is_set():
            face = self.face
            beats = face.beats if face in self.built and TICK else 0
            if not beats:
                self.stopping.wait(0.2)
                continue

            beat = math.floor(time.time() * beats) + 1        # the number of the next beat since 1970
            if self.stopping.wait(max(0.0, beat / beats - time.time())):
                return

            now = datetime.datetime.fromtimestamp(beat // beats)
            if face is self.face and self.visible and self.soundOn and not self.quietTime(now):
                sound = face.beatSound(now, beat % beats)
                if sound is not None:
                    sound.play()


    def enter(self):
        self.visible = True
        self.face.enter()


    # The ticking stops; the bells too, unless they are meant to be heard behind the other screens
    def leave(self):
        self.visible = False
        if not CHIME_WHEN_HIDDEN:
            self.silence()


    def silence(self):
        self.due = []
        for sound in self.playing:
            sound.stop()
        self.playing = []


    # The SOUND button sets only how loud the ticks are (and turns them off): the chimes are
    # always heard, as loud as CLOCK_CHIME_VOLUME
    def soundList(self):
        return [(sound, 1.0) for face in self.built for sound in face.tickSounds() if sound is not None]

    def volumeNotice(self, level):
        return f"{self.name}   TICK OFF" if level == 0 else f"{self.name}   TICK {self.volumes[level][0]}"

    # Whether sounds of this kind ("chime" or "tick") are on at all
    def kindOn(self, kind):
        return self.chimesOn if kind == "chime" else TICK


    # A notice in the middle of the screen for a moment (the face's name, or the chimes on or off)
    def showNotice(self, text, colour=NOTICE_COLOUR):
        self.notice = (scr.makeNotice(text, colour), pygame.time.get_ticks())
        self.noticeShown = False


    # OK (pressed briefly) changes the face; held down, it plays the face's last chime again
    def handleEvent(self, event):
        if event.type == scr.OK_PRESSED or (event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_SPACE)):
            self.silence()
            if self.face in self.built:
                self.lastFace = self.face
            self.index = (self.index + 1) % len(self.faces)
            print(f"Clock: {self.face.name}")
            self.face.enter()
            self.status = None
            self.showNotice(f"{self.name}   {self.face.name}")

        # SOUND held down (or C) turns the chimes off, or back on
        elif event.type == scr.SOUND_HELD or (event.type == pygame.KEYDOWN and event.key == pygame.K_c):
            self.chimesOn = not self.chimesOn
            print(f"Clock: chimes {'on' if self.chimesOn else 'off'}")
            if not self.chimesOn:
                self.silence()
            self.status = None
            self.showNotice(f"{self.name}   CHIMES {'ON' if self.chimesOn else 'OFF'}",
                            (255, 153, 0) if self.chimesOn else (230, 61, 61))

        elif event.type == scr.OK_HELD or (event.type == pygame.KEYDOWN and event.key == pygame.K_DELETE):
            self.silence()
            if self.chimesOn:
                self.play(self.lastChime(datetime.datetime.now()))


    # The face's chime for the last quarter that had one, going back up to an hour
    def lastChime(self, now):
        at = now.replace(minute=now.minute // 15 * 15, second=0, microsecond=0)
        for _ in range(5):
            sounds = self.face.chime(at.hour, at.minute)
            if sounds:
                return sounds
            at -= datetime.timedelta(minutes=15)
        return []


    # Start the sounds now, or later: [(seconds later, Sound)]
    def play(self, sounds):
        ticks = pygame.time.get_ticks()
        for later, sound in sounds:
            if sound is not None:
                self.due.append((ticks + later * 1000, sound))
        self.due.sort(key=lambda d: d[0])


    # Whether it is the time of night when the clock is silent
    @staticmethod
    def quietTime(now):
        if QUIET_FROM <= QUIET_UNTIL:
            return QUIET_FROM <= now.hour < QUIET_UNTIL
        return now.hour >= QUIET_FROM or now.hour < QUIET_UNTIL


    # The words in the corner: at night, that the clock is silent
    def statusFor(self, now):
        if (self.chimesOn or (self.soundOn and TICK)) and self.quietTime(now):
            return f"Silent until {QUIET_UNTIL % 12 or 12}{'AM' if QUIET_UNTIL < 12 else 'PM'}"
        return None


    def update(self, visible):
        # a face not drawn yet is drawn once its name has been shown, as drawing it takes a moment
        if self.face not in self.built:
            if not (visible and self.noticeShown):
                return
            self.build(self.face)
            if self.notice:
                self.notice = (self.notice[0], pygame.time.get_ticks())

        now = datetime.datetime.now()

        # as each second begins, the face's sounds for it
        if now.second != self.lastSecond:
            self.lastSecond = now.second
            if not self.quietTime(now):
                self.play([(later, sound) for later, sound, kind in self.face.soundsAt(now) if self.kindOn(kind) and
                           (visible and self.soundOn if kind == "tick" else visible or CHIME_WHEN_HIDDEN)])

        ticks = pygame.time.get_ticks()
        while self.due and ticks >= self.due[0][0]:
            sound = self.due.pop(0)[1]
            sound.play()
            self.playing = [s for s in self.playing if s.get_num_channels()] + [sound]

        if not visible:
            return

        status = self.statusFor(now)
        if status != self.status:
            self.status = status
            face = self.face
            font = sysFont(face.statusFonts, 30, italic=face.statusItalic)
            self.statusImage = font.render(status, True, face.statusColour) if status else None

        self.face.update(now)


    def draw(self, surface):
        (self.face if self.face in self.built else self.lastFace).draw(surface)
        if self.statusImage:
            surface.blit(self.statusImage, self.statusImage.get_rect(bottomright=STATUS_CORNER))

        if self.notice:
            picture, shown = self.notice
            age = (pygame.time.get_ticks() - shown) / 1000
            if age > NOTICE_SECONDS:
                self.notice = None
            else:
                picture.set_alpha(int(255 * min(1.0, (NOTICE_SECONDS - age) / 0.4)))
                surface.blit(picture, picture.get_rect(center=(scr.SCREEN_WIDTH // 2, scr.SCREEN_HEIGHT // 2)))
                self.noticeShown = True
