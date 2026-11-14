# lcars_shapes.py

import math
import operator
import os
import random
import datetime
import time
import pygame
from enum import Enum

import fonts


# Its settings are in settings.py (next to lcars.py)
from settings import (
    SHAPES_SCROLL_HOLD as SCROLL_HOLD,
    SHAPES_SCROLL_SPEED as SCROLL_SPEED,
    SHAPES_SCROLL_PAD as SCROLL_PAD,
    SHAPES_SCROLL_MAX_MESSAGES as SCROLL_MAX_MESSAGES,
    SHAPES_TICKER_SPEED as TICKER_SPEED,
    SHAPES_TICKER_SEPARATOR as TICKER_SEPARATOR,
    SHAPES_TWINKLE_FAST as TWINKLE_FAST,
    SHAPES_TWINKLE_MEDIUM as TWINKLE_MEDIUM,
    SHAPES_TWINKLE_SLOW as TWINKLE_SLOW,
    SHAPES_TWINKLE_VERYSLOW as TWINKLE_VERYSLOW,
    SHAPES_TWINKLE_SPREAD as TWINKLE_SPREAD,
    SHAPES_GRAPH_BAR_FRACTION as GRAPH_BAR_FRACTION,
    SHAPES_GRAPH_DOT_MIN as GRAPH_DOT_MIN,
    SHAPES_GRAPH_DOT_MAX as GRAPH_DOT_MAX,
    SHAPES_GRAPH_PULSE_SECONDS as GRAPH_PULSE_SECONDS,
    SHAPES_BAR_TEXT_PAD as BAR_TEXT_PAD,
    SHAPES_RADAR_MARGIN as RADAR_MARGIN,
    SHAPES_RADAR_TAB_SIZE as RADAR_TAB_SIZE,
    SHAPES_RADAR_TICK_DEGREES as RADAR_TICK_DEGREES,
    SHAPES_RADAR_LONG_TICK_DEGREES as RADAR_LONG_TICK_DEGREES,
    SHAPES_RADAR_SWEEP_SECONDS as RADAR_SWEEP_SECONDS,
    SHAPES_RADAR_SWEEP_GLOW_DEGREES as RADAR_SWEEP_GLOW_DEGREES,
    SHAPES_RADAR_SWEEP_GLOW_ALPHA as RADAR_SWEEP_GLOW_ALPHA,
    SHAPES_RADAR_FLARE_DEGREES as RADAR_FLARE_DEGREES,
    SHAPES_RADAR_FLARE_AMOUNT as RADAR_FLARE_AMOUNT,
    SHAPES_RADAR_MARKER_GAP as RADAR_MARKER_GAP,
    SHAPES_RADAR_LABEL_GAP as RADAR_LABEL_GAP,
    SHAPES_CASCADE_INTERVAL as CASCADE_INTERVAL,
    SHAPES_CASCADE_CHANGES as CASCADE_CHANGES,
    SHAPES_CASCADE_PAD as CASCADE_PAD,
    SHAPES_SEARCH_ROWS as SEARCH_ROWS,
    SHAPES_SEARCH_SEGMENTS as SEARCH_SEGMENTS,
    SHAPES_SEARCH_GAP as SEARCH_GAP,
    SHAPES_SEARCH_TRAIL as SEARCH_TRAIL,
    SHAPES_SEARCH_MIN_SPEED as SEARCH_MIN_SPEED,
    SHAPES_SEARCH_MAX_SPEED as SEARCH_MAX_SPEED,
    SHAPES_SEARCH_UNLIT as SEARCH_UNLIT,
    SHAPES_SEARCH_HEAD_WHITE as SEARCH_HEAD_WHITE,
    SHAPES_SEARCH_DOT_SECONDS as SEARCH_DOT_SECONDS,
    SHAPES_SEARCH_TITLE_HEIGHT as SEARCH_TITLE_HEIGHT,
    SHAPES_SEARCH_SUBTITLE_HEIGHT as SEARCH_SUBTITLE_HEIGHT,
    SHAPES_POPUP_WIDTH as POPUP_WIDTH,
    SHAPES_POPUP_FRAME as POPUP_FRAME,
    SHAPES_POPUP_RADIUS as POPUP_RADIUS,
    SHAPES_POPUP_TITLE_HEIGHT as POPUP_TITLE_HEIGHT,
    SHAPES_POPUP_BAND_HEIGHTS as POPUP_BAND_HEIGHTS,
    SHAPES_POPUP_PAD as POPUP_PAD,
    SHAPES_POPUP_FLASH_HZ as POPUP_FLASH_HZ,
    SHAPES_METER_DIM as METER_DIM,
    SHAPES_TEXT_CONTRAST_THRESHOLD as TEXT_CONTRAST_THRESHOLD,
    SHAPES_ICON_SCALES as ICON_SCALES,
    SHAPES_HELICOPTER_SPIN as HELICOPTER_SPIN,
)

 


 












# ---------------------------------------------------------------------------
# Palette - classic LCARS colours. Mix and match; avoid using more than
# 4-5 colours in one layout or it stops reading as LCARS.
# ---------------------------------------------------------------------------
class Colours:

    BLACK       = (0, 0, 0)
    BACKGROUND  = (0, 0, 0)
    ORANGE      = (255, 153, 0)
    PALE_ORANGE = (255, 160, 90)
    BUTTERSCOTCH= (255, 204, 102)
    LILAC       = (204, 153, 255)
    PALE_BLUE   = (153, 153, 204)
    BLUE        = (132, 132, 255)
    ICE_BLUE    = (153, 204, 255)
    RED         = (230, 61, 61)
    SALMON      = (255, 102, 102)
    TAN         = (255, 204, 153)
    WHITE       = (255, 255, 255)
    DARK_GREY   = (20, 20, 20)
    LIGHT_GREY   = (80, 80, 80)

    # The accent colours a shape picks from when no colour is given
    LCARS_COLOURS = (
        ORANGE, PALE_ORANGE, BUTTERSCOTCH, LILAC,
        PALE_BLUE, BLUE, ICE_BLUE, RED, SALMON, TAN,
    )

class Alignment(Enum):
    LEFT = 101
    RIGHT = 102
    CENTRE = 103
    
class Direction(Enum):    
    VERTICAL = 201
    HORIZONTAL = 202

class GraphStyle(Enum):
    LINE = 501
    BAR = 502


class TwinkleRate(Enum):
    FAST = 401
    MEDIUM = 402
    SLOW = 403
    FAST_RANDOM = 404
    MEDIUM_RANDOM = 405
    SLOW_RANDOM = 406
    VERYSLOW_RANDOM = 407

    # True for the _RANDOM rates, which vary the gap between flips
    @property
    def isRandom(self):
        return self in (TwinkleRate.FAST_RANDOM, TwinkleRate.MEDIUM_RANDOM, 
                        TwinkleRate.SLOW_RANDOM, TwinkleRate.VERYSLOW_RANDOM)

    # Seconds between flips (the average, for the random rates)
    @property
    def period(self):
        if self in (TwinkleRate.FAST, TwinkleRate.FAST_RANDOM):
            return TWINKLE_FAST

        if self in (TwinkleRate.MEDIUM, TwinkleRate.MEDIUM_RANDOM):
            return TWINKLE_MEDIUM

        if self in (TwinkleRate.SLOW, TwinkleRate.SLOW_RANDOM):
            return TWINKLE_SLOW

        return TWINKLE_VERYSLOW
    


# Black text reads better on the pale colours, white on the dark ones.
# Weightings are the usual ones for perceived brightness - green looks
# brighter than red, which looks brighter than blue, at the same value.
def textColourFor(colour):
    brightness = (colour[0] * 299 + colour[1] * 587 + colour[2] * 114) / 1000

    if brightness > TEXT_CONTRAST_THRESHOLD:
        return Colours.BLACK

    return Colours.WHITE


# A darkened version of a colour, used for the unlit meter segments
# A colour part of the way from colour1 (fraction 0) to colour2 (fraction 1)
def mixColours(colour1, colour2, fraction):
    return tuple(round(a + (b - a) * fraction) for a, b in zip(colour1, colour2))


def dimColour(colour):
    return tuple(int(c * METER_DIM) for c in colour)



class LcarsShape:
    
    def __init__(self, surface, x, y, w, h, colour):
        self._surface = surface
        self._x = x
        self._y = y
        self._w = w
        self._h = h
        self._needsUpdate = True
        if colour:
            self._colour = colour
        else:
            self._colour = random.choice(Colours.LCARS_COLOURS)

    @property
    def colour(self):
        return self._colour          
       
    @colour.setter
    def colour(self, colour):
        self._colour = colour
        self._needsUpdate = True

            
    
    def update(self):
        if self._needsUpdate:
            self._needsUpdate = False
            self.draw()


    
class LcarsTextShape(LcarsShape):

    def __init__(self, surface, x, y, w, h, colour, text, textSize, alignment):
                
        super().__init__(surface, x, y, w, h, colour)
        
        assert isinstance(textSize, fonts.TextSize), "Invalid textSize argument"
        assert isinstance(alignment, Alignment), "Invalid alignment argument"
        
        # Check the resolved colour - colour=None means the parent picked one at random
        assert isinstance(self._colour, tuple) and len(self._colour) == 3, "Invalid Colour argument"
        
        self._text = text
        self._textSize = textSize
        self._textAlign = alignment
        self._textColour = None     # None means pick automatically from the shape's colour


    @property
    def text(self):
        return self._text
                
    @text.setter
    def text(self, value):
        if (self._text != value):
            self._text = value
            self._needsUpdate = True
    
    
    @property
    def textSize(self):
        return self._textSize
        
    @textSize.setter
    def textSize(self, value):
        assert isinstance(value, fonts.TextSize), "Invalid textSize argument"
        self._textSize = value
        self._needsUpdate = True
    
    
    @property
    def textAlign(self):
        return self._textAlign
        
    @textAlign.setter
    def textAlign(self, value):
        assert isinstance(value, Alignment), "Invalid alignment argument"
        self._textAlign = value
        self._needsUpdate = True
    
    
    # Follows the shape's colour unless one has been set explicitly.
    # Set it back to None to go automatic again.
    @property
    def textColour(self):
        if self._textColour:
            return self._textColour

        return textColourFor(self._colour)
        
    @textColour.setter
    def textColour(self, value):
        assert value is None or (isinstance(value, tuple) and len(value) == 3), \
            "Invalid Colour argument. RGB tuple or None expected."
        self._textColour = value
        self._needsUpdate = True


    def drawText(self, pad):
        if not self._text:
            return

        font = fonts.fontFor(self._textSize)

        img = font.render(self.text.upper(), True, self.textColour)

        if self._textAlign == Alignment.RIGHT:
            x = self._x + self._w - pad - img.get_width()
        elif self._textAlign == Alignment.LEFT:
            x = self._x + pad
        else:  # CENTRE
            x = self._x + (self._w - img.get_width()) // 2
        

        capTop, capHeight = fonts.capMetricsFor(self._textSize)
        y = self._y + (self._h - capHeight) // 2 - capTop

        self._surface.blit(img, (x, y))


# Static text object with no background.
# The shape has zero width and height, so the text is centred vertically on
# y + 20 (LABEL_Y_OFFSET), and (x) is its left edge, centre or right edge
# depending on the alignment. Nothing clears the old text, so it's meant for
# text that doesn't change.
LABEL_Y_OFFSET = 20

class Label(LcarsTextShape):

    def __init__(self, surface, x, y, text="Label", colour=Colours.WHITE,
                 alignment=Alignment.CENTRE, textSize=fonts.TextSize.MEDIUM):

        super().__init__(surface, x, y + LABEL_Y_OFFSET, 0, 0, Colours.BACKGROUND, text, textSize, alignment)
        self._textColour=colour
        
        
    def draw(self):        
        self.drawText(0)      
        self._needsUpdate = False
    

# Round dot.
class Dot(LcarsShape):
     
    def __init__(self, surface, x, y, w, colour=None):

        super().__init__(surface, x, y, w, None, colour)
                
        
    def draw(self):
        
        self._needsUpdate = False
        radius = self._w // 2
        pygame.draw.circle(self._surface, self._colour, (self._x, self._y), radius)
    


# Image or Icon.
class Image(LcarsShape):
     
    def __init__(self, surface, x, y, image=None):

        super().__init__(surface, x, y, None, None, None)
        self._image = image
                
                
    @property
    def image(self):
        return self._image
                
    @image.setter
    def image(self, value):
        self._image = value
        self._needsUpdate = True

       
    def draw(self):        
        self._needsUpdate = False

        # Erase the old image
        if self._w and self._h:
            self._surface.fill(Colours.BACKGROUND, (self._x, self._y, self._w, self._h))
            
        if self._image is None:                 
            self._w = None
            self._h = None
        else:
            self._surface.blit(self._image, (self._x, self._y))
            self._w = self._image.get_width()
            self._h = self._image.get_height()
        


 
# Fully rounded 'stadium' shape - a horizontal bar with semicircle ends
class Pill(LcarsTextShape):
    
    def __init__(self, surface, x, y, w, h, colour=None, text=None, 
                 alignment=Alignment.CENTRE, textSize=fonts.TextSize.MEDIUM):

        super().__init__(surface, x, y, w, h, colour, text, textSize, alignment)
                
        
    def draw(self):
        
        self._needsUpdate = False
        radius = self._h // 2
        pygame.draw.rect(self._surface, self._colour, (self._x + radius, self._y, self._w - 2 * radius, self._h))
        pygame.draw.circle(self._surface, self._colour, (self._x + radius, self._y + radius), radius)
        pygame.draw.circle(self._surface, self._colour, (self._x + self._w - radius, self._y + radius), radius)
    
        if self._text:
            self.drawText(radius)
   
  
   
# A rounded end-cap only on one side, square on the other
class HalfPill(LcarsTextShape):

    def __init__(self, surface, x, y, w, h, colour=None, text=None, 
                 alignment=Alignment.LEFT, textSize=fonts.TextSize.MEDIUM ):

        super().__init__(surface, x, y, w, h, colour, text, textSize, alignment)
        

    def draw(self):
        
        self._needsUpdate = False
        radius = self._h // 2
        if self._textAlign == Alignment.LEFT:
            pygame.draw.rect(self._surface, self._colour, (self._x + radius, self._y, self._w - radius, self._h))
            pygame.draw.circle(self._surface, self._colour, (self._x + radius, self._y + radius), radius)
        else:
            pygame.draw.rect(self._surface, self._colour, (self._x, self._y, self._w - radius, self._h))
            pygame.draw.circle(self._surface, self._colour, (self._x + self._w - radius, self._y + radius), radius)

        if self._text:
            self.drawText(radius)
 
 
 
# Plain square-cornered bar. 
class Bar(LcarsTextShape):

    def __init__(self, surface, x, y, w, h, colour=None, text=None,
                 alignment=Alignment.LEFT, textSize=fonts.TextSize.MEDIUM ):

        super().__init__(surface, x, y, w, h, colour, text, textSize, alignment)


    def draw(self):
        self._needsUpdate = False
        pygame.draw.rect(self._surface, self._colour, (self._x, self._y, self._w, self._h))
        
        if self._text:
            self.drawText(BAR_TEXT_PAD)
 


 
# The radius of the pulsing dot on a graph at this moment, GRAPH_DOT_MIN to GRAPH_DOT_MAX
def dotRadius():
    phase = (time.perf_counter() % GRAPH_PULSE_SECONDS) / GRAPH_PULSE_SECONDS
    swell = 0.5 - 0.5 * math.cos(2 * math.pi * phase)       # 0 up to 1 and back to 0, once per pulse
    return round(GRAPH_DOT_MIN + swell * (GRAPH_DOT_MAX - GRAPH_DOT_MIN))


# Line or bar graph of values against Unix timestamps, with a day-of-week axis.
# The style is GraphStyle.LINE (the default) or GraphStyle.BAR. A bar graph
# always includes zero on its value axis, and the bars grow up or down from it.
# The current hour has a white dot that pulses. Only the dot is redrawn when it
# pulses, not the whole graph.
# NOTE: (x, y) is the BOTTOM-LEFT corner. Missing (None) values are skipped.
class Graph(LcarsShape):

    def __init__(self, surface, x, y, w, h, colour, title, timestamps, values,
                 formatString="{:.1f}", style=GraphStyle.LINE):

        assert isinstance(style, GraphStyle), "Invalid style argument"

        super().__init__(surface, x, y, w, h, colour)
        self._timestamps = timestamps
        self._values = values
        self._formatString = formatString
        self._title = title
        self._style = style
        self._dot = None            # where the current hour's dot is, or None if there isn't one
        self._dotRect = None        # the square the dot can swell to fill...
        self._dotBehind = None      # ...and what was there before the dot was drawn
        self._dotRadius = None      # the size the dot is drawn at now
        self._dotCentre = None      # where it is drawn, in whole pixels


    @property
    def style(self):
        return self._style

    @style.setter
    def style(self, value):
        assert isinstance(value, GraphStyle), "Invalid style argument"
        self._style = value
        self._needsUpdate = True


    @property
    def timestamps(self):
        return self._timestamps
                
    @timestamps.setter
    def timestamps(self, value):
        self._timestamps = value
        self._needsUpdate = True
    
    @property
    def values(self):
        return self._values
                
    @values.setter
    def values(self, values):
        self._values = values
        self._needsUpdate = True
         
         
    # Redraws the whole graph if its data has changed, otherwise only the pulsing dot
    def update(self):
        if self._needsUpdate:
            self.draw()
        elif self._dot is not None:
            self.pulseDot()


    def draw(self):
        # clear the background
        self._needsUpdate = False
        self._dot = None
        pygame.draw.rect(self._surface, Colours.DARK_GREY, (self._x, self._y - self._h, self._w, self._h))
        
        graphLeft = self._x + 40
        graphBottom = self._y - 30
        graphWidth = self._w - 40
        graphHeight = self._h - 40

        # X and Y axes
        pygame.draw.line(self._surface, Colours.WHITE, (graphLeft, graphBottom), (graphLeft + graphWidth - 1, graphBottom), width=1)
        pygame.draw.line(self._surface, Colours.WHITE, (graphLeft, graphBottom), (graphLeft, graphBottom - graphHeight), width=1)
            
        if not self._values or not self._timestamps:
            return
            
        numberOfValues = len(self._values)
        numberOfTimestamps = len(self._timestamps)
        assert numberOfValues == numberOfTimestamps, "Invalid data in Graph.draw"

        # Open-Meteo can return null for some hours - leave those out
        validValues = [v for v in self._values if v is not None]
        if not validValues:
            return

        minValue = min(validValues)
        maxValue = max(validValues)

        # Bars must start from zero, or their heights would be misleading
        if self._style == GraphStyle.BAR:
            minValue = min(minValue, 0)
            maxValue = max(maxValue, 0)

        valueRange = maxValue - minValue
        if valueRange == 0:
            valueRange = 1      # flat line - avoid dividing by zero
        xScale = graphWidth / numberOfValues
        yScale = graphHeight / valueRange
        font = fonts.fontFor(fonts.TextSize.XS)

        
        # Draw the left axis and horizontal lines
        for i in range(0,5):
            y1 = graphBottom - i*graphHeight/4
            
            pygame.draw.line(self._surface, Colours.WHITE, (graphLeft-7, y1), (graphLeft-1, y1), width=1)
            if i != 0:
                pygame.draw.line(self._surface, Colours.LIGHT_GREY, 
                    (graphLeft+1, y1), (graphLeft+graphWidth, y1), width=1)
                    
            # Rounding error can leave a tiny negative where zero should be,
            # which would be labelled "-0". Rounding and adding 0.0 stops that.
            v = round(minValue + valueRange/4 * i, 9) + 0.0
            text = self._formatString.format(v)
            img = font.render(text, True, Colours.WHITE)
            x2 = graphLeft - img.get_width() - 10
            y2 = y1 - img.get_height() // 2
            self._surface.blit(img, (x2, y2)) 
                          
        # Print the bottom axis and vertical lines
        graphRight = graphLeft + graphWidth
        lastDayOfWeek = None
        for i, t in enumerate(self._timestamps):
            dayOfWeek = datetime.datetime.fromtimestamp(t).strftime("%a").upper()
            if dayOfWeek == lastDayOfWeek:
                continue
            lastDayOfWeek = dayOfWeek

            x1 = graphLeft + i*xScale
            img = font.render(dayOfWeek, True, Colours.WHITE)

            # A day that only has a sliver of the graph left has no room for its label
            if x1 + 8 + img.get_width() > graphRight:
                continue

            pygame.draw.line(self._surface, Colours.WHITE, (x1, graphBottom), (x1, graphBottom+8), width=1)
            if i != 0:
                pygame.draw.line(self._surface, Colours.LIGHT_GREY,
                    (x1, graphBottom-1), (x1, graphBottom-graphHeight), width=1)

            self._surface.blit(img, (x1+8, graphBottom+3))


        # print the title
        img = font.render(self._title, True, Colours.WHITE)
        self._surface.blit(img, (graphLeft + (graphWidth - img.get_width())/2 , self._y - self._h + 2))
                   

        if self._style == GraphStyle.BAR:
            self.drawBars(graphLeft, graphBottom, xScale, yScale, minValue)
        else:
            self.drawLine(graphLeft, graphBottom, xScale, yScale, minValue)

        # Last, so that nothing is drawn over it
        self.drawDot()


    # Draw the dot on the current hour (if there is one), keeping what is under it first
    # so that pulseDot can put that back
    def drawDot(self):
        if self._dot is None:
            return

        # The centre is a whole number of pixels, so that the dot is drawn in the same place that the
        # square it can swell to fill (and so the pixels saved from behind it) is worked out for
        self._dotCentre = (round(self._dot[0]), round(self._dot[1]))
        x, y = self._dotCentre
        size = 2 * GRAPH_DOT_MAX + 1
        self._dotRect = pygame.Rect(x - GRAPH_DOT_MAX, y - GRAPH_DOT_MAX, size, size).clip(self._surface.get_rect())
        self._dotBehind = self._surface.subsurface(self._dotRect).copy()
        self._dotRadius = dotRadius()

        pygame.draw.circle(self._surface, Colours.WHITE, self._dotCentre, self._dotRadius)


    # Redraw the dot if it has changed size
    def pulseDot(self):
        radius = dotRadius()
        if radius == self._dotRadius:
            return

        self._dotRadius = radius
        self._surface.blit(self._dotBehind, self._dotRect.topleft)
        pygame.draw.circle(self._surface, Colours.WHITE, self._dotCentre, radius)


    # Draw the values as a line. Points are keyed by their index so a missing
    # value just leaves a straight join between its neighbours.
    def drawLine(self, graphLeft, graphBottom, xScale, yScale, minValue):

        points = {i: (graphLeft + i * xScale + xScale / 2, graphBottom - (v - minValue) * yScale)
                  for i, v in enumerate(self._values) if v is not None}

        # draw.lines needs at least two points
        if len(points) >= 2:
            pygame.draw.lines(self._surface, self._colour, False, list(points.values()), width=2)
        else:
            for point in points.values():
                pygame.draw.circle(self._surface, self._colour, point, 2)

        # The current hour gets the dot (drawn later, by drawDot)
        currentHour = int(time.time()) // 3600
        for i, t in enumerate(self._timestamps):
            if t // 3600 == currentHour and i in points:
                self._dot = points[i]


    # Draw the values as bars, one per value, rising (or falling, if negative)
    # from the zero line. A missing value just leaves a gap.
    def drawBars(self, graphLeft, graphBottom, xScale, yScale, minValue):

        zeroY = graphBottom - (0 - minValue) * yScale
        currentHour = int(time.time()) // 3600
        barWidth = max(1, int(xScale * GRAPH_BAR_FRACTION))
        dot = None      # where the current hour's white dot goes, if it has a value

        for i, v in enumerate(self._values):
            if v is None:
                continue

            # Every bar is the same width, centred in its own slice of the x
            # axis. The width is only part of the slice (see GRAPH_BAR_FRACTION)
            # so there is always a gap between bars, as long as each slice
            # is at least 2 pixels wide.
            centre = graphLeft + (i + 0.5) * xScale
            x0 = round(centre - barWidth / 2)

            valueY = graphBottom - (v - minValue) * yScale
            top = round(min(zeroY, valueY))
            height = round(abs(zeroY - valueY))

            # A small value still gets a bar one pixel high, so it can be seen
            if v != 0:
                height = max(1, height)

            pygame.draw.rect(self._surface, self._colour, (x0, top, barWidth, height))

            # The current hour gets a white dot on the end of its bar (at the
            # zero line if the value is 0). The bar itself keeps its colour.
            if self._timestamps[i] // 3600 == currentHour:
                if v >= 0:
                    tipY = top
                else:
                    tipY = top + height - 1
                dot = (x0 + (barWidth - 1) // 2, tipY)

        # Drawn later, by drawDot, so that no bar covers any part of it
        self._dot = dot



# The outline of an aircraft icon, as (x, y) points with its nose pointing up
# (negative y). It is 2 long, so the nose is 1 from the centre.
PLANE_OUTLINE = (
    (0.00, -1.00), (0.10, -0.80), (0.12, -0.25), (0.95, 0.20), (0.95, 0.40),
    (0.12, 0.20), (0.10, 0.65), (0.38, 0.88), (0.38, 1.00), (0.00, 0.92),
    (-0.38, 1.00), (-0.38, 0.88), (-0.10, 0.65), (-0.12, 0.20), (-0.95, 0.40),
    (-0.95, 0.20), (-0.12, -0.25), (-0.10, -0.80),
)


# The outlines of the icons for the other kinds of aeroplane, in the same form. A light
# aircraft has straight wings, and a fast one (a fighter) has swept back ones.
PLANE_LIGHT = (
    (0.00, -1.00), (0.12, -0.70), (0.12, -0.20), (0.95, -0.15), (0.95, 0.10),
    (0.12, 0.10), (0.10, 0.70), (0.45, 0.85), (0.45, 1.00), (-0.45, 1.00),
    (-0.45, 0.85), (-0.10, 0.70), (-0.12, 0.10), (-0.95, 0.10), (-0.95, -0.15),
    (-0.12, -0.20), (-0.12, -0.70),
)

PLANE_FAST = (
    (0.00, -1.00), (0.12, -0.50), (0.90, 0.55), (0.90, 0.80), (0.14, 0.55),
    (0.12, 0.80), (0.35, 1.00), (-0.35, 1.00), (-0.12, 0.80), (-0.14, 0.55),
    (-0.90, 0.80), (-0.90, 0.55), (-0.12, -0.50),
)

# The kinds (see Aircraft.kind) that don't use PLANE_OUTLINE, and how big each kind is drawn
# compared with the size asked for: heavy aircraft are bigger and light ones smaller. A kind
# that isn't here (or None, for one that doesn't say) is drawn at the size asked for.
ICON_OUTLINES = {"LIGHT": PLANE_LIGHT, "FAST": PLANE_FAST}


# How much bigger or smaller than the size asked for a kind of aircraft is drawn
def iconScale(kind):
    return ICON_SCALES.get(kind, 1.0)


# The screen positions of the points of an outline centred on (cx, cy), `size` pixels
# from the centre to the nose, heading `heading_deg` degrees clockwise from the top of the
# screen (0 = north, 90 = east).
def outlinePoints(outline, cx, cy, size, heading_deg):
    angle = math.radians(heading_deg)
    sin_a = math.sin(angle)
    cos_a = math.cos(angle)

    points = []
    for px, py in outline:
        points.append((cx + size * (px * cos_a - py * sin_a),
                       cy + size * (px * sin_a + py * cos_a)))
    return points


# The screen positions of the points of the usual aircraft icon (see outlinePoints)
def planePoints(cx, cy, size, heading_deg):
    return outlinePoints(PLANE_OUTLINE, cx, cy, size, heading_deg)


# A helicopter seen from above: a round body, a tail pointing away from the way it is
# heading, and two blades that turn, `spin` degrees round from the way it is heading.
def drawHelicopter(surface, cx, cy, size, heading_deg, colour, spin):
    tail = math.radians(heading_deg + 180)
    pygame.draw.line(surface, colour, (cx, cy), (cx + size * math.sin(tail), cy - size * math.cos(tail)), 2)
    pygame.draw.circle(surface, colour, (cx, cy), max(2, round(size * 0.3)))

    for blade in (spin, spin + 90):
        angle = math.radians(heading_deg + blade)
        dx = size * 0.9 * math.sin(angle)
        dy = size * 0.9 * math.cos(angle)
        pygame.draw.line(surface, colour, (cx - dx, cy + dy), (cx + dx, cy - dy), 1)


# An aircraft icon of this kind (see Aircraft.kind) centred on (cx, cy). `size` is its size
# for an ordinary aircraft: the kind makes it bigger or smaller. Its heading is None for a plain dot.
def drawAircraftIcon(surface, cx, cy, size, heading_deg, colour, kind, spin=0.0):
    size = size * iconScale(kind)

    if heading_deg is None:
        pygame.draw.circle(surface, colour, (cx, cy), max(2, round(size / 3)))
    elif kind == "HELICOPTER":
        drawHelicopter(surface, cx, cy, size, heading_deg, colour, spin)
    else:
        pygame.draw.polygon(surface, colour, outlinePoints(ICON_OUTLINES.get(kind, PLANE_OUTLINE), cx, cy, size, heading_deg))


# A marker round an icon: ("circle", colour) is a ring, ("brackets", colour) is a bracket at
# each of the four corners of a square, `radius` pixels out from (cx, cy)
def drawMarker(surface, cx, cy, radius, marker):
    shape, colour = marker

    if shape == "circle":
        pygame.draw.circle(surface, colour, (cx, cy), radius, 2)
        return

    if shape == "diamond":
        pygame.draw.polygon(surface, colour, ((cx, cy - radius), (cx + radius, cy), (cx, cy + radius), (cx - radius, cy)), 2)
        return

    reach = radius // 2
    for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        cornerX = cx + sx * radius
        cornerY = cy + sy * radius
        pygame.draw.line(surface, colour, (cornerX, cornerY), (cornerX - sx * reach, cornerY), 2)
        pygame.draw.line(surface, colour, (cornerX, cornerY), (cornerX, cornerY - sy * reach), 2)


# Where on the screen a point goes on a radar centred on (centreX, centreY):
# `distance` away (as a fraction of rangeMax, which is `radius` pixels) in the
# direction `bearing_deg` (degrees true, 0 = north, 90 = east).
def radarPosition(centreX, centreY, radius, rangeMax, bearing_deg, distance):
    fromCentre = min(distance, rangeMax) / rangeMax * radius
    angle = math.radians(bearing_deg)
    return centreX + fromCentre * math.sin(angle), centreY - fromCentre * math.cos(angle)



# The glow behind a radar's sweep line: a slice of a circle `radius` pixels long and
# RADAR_SWEEP_GLOW_DEGREES wide, brightest next to the line and fading away behind it.
# It is drawn pointing north with its tip in the bottom right corner of the picture
# (which is as small as it can be), so that it can be turned about the tip to follow
# the sweep line.
def makeSweepGlow(radius, colour):
    width = math.ceil(radius * math.sin(math.radians(RADAR_SWEEP_GLOW_DEGREES))) + 1
    height = radius + 1
    glow = pygame.Surface((width, height), pygame.SRCALPHA)
    tipX = width - 1
    tipY = height - 1

    # Lines a quarter of a degree apart, the furthest behind the sweep line first so
    # that the brighter ones nearer it are drawn over them
    steps = RADAR_SWEEP_GLOW_DEGREES * 4
    for step in range(steps, -1, -1):
        behind = step / steps           # 0 at the sweep line, 1 at the far edge of the glow
        alpha = round(RADAR_SWEEP_GLOW_ALPHA * (1 - behind) ** 2)
        angle = math.radians(-behind * RADAR_SWEEP_GLOW_DEGREES)
        end = (tipX + radius * math.sin(angle), tipY - radius * math.cos(angle))
        pygame.draw.line(glow, (*colour, alpha), (tipX, tipY), end, 2)

    return glow


# The colour of an aircraft on the radar: its own, but lit up towards white when the
# sweep has just passed it, fading back over RADAR_FLARE_DEGREES.
def flareColour(colour, bearing, sweepBearing):
    behind = (sweepBearing - bearing) % 360         # how far the sweep has gone past it

    if behind >= RADAR_FLARE_DEGREES:
        return colour

    return mixColours(colour, Colours.WHITE, RADAR_FLARE_AMOUNT * (1 - behind / RADAR_FLARE_DEGREES))


# A radar-style display seen from above, with north at the top and the
# receiver at the centre. The circle covers distances up to rangeMax, with a
# ring every ringStep. (x, y) is the TOP-LEFT corner of the square it fits in.
#
# It is an animated shape that is redrawn every frame: a sweep line goes round with a
# glow behind it, and the aircraft light up as it passes. Everything that never moves
# (the circle, rings, compass ring, runways and so on) is drawn once into a picture
# that is copied in each frame, and is only drawn again if the colour, markers or lines change.
#
# Each blip is a tuple of 9 values:
#   (bearing_deg, distance, heading_deg, size, colour, label, trail, kind, marker)
#   bearing_deg   direction from the centre to the blip, degrees true (0 = north)
#   distance      how far from the centre, in the same units as rangeMax
#   heading_deg   direction it is travelling, degrees true. The blip is drawn
#                 as an aircraft icon rotated to point that way, or as a plain
#                 dot if this is None
#   size          pixels from the centre of the icon to its nose
#   colour        the icon's colour
#   label         a short text drawn beside the icon in white, or None
#   trail         where it has been: a sequence of (bearing_deg, distance), oldest
#                 first, drawn as a line fading away behind the icon (can be empty)
#   kind          the kind of aircraft ('LIGHT', 'HEAVY', 'HELICOPTER'...), which gives the
#                 icon its shape and a bigger or smaller size (see drawAircraftIcon), or None
#   marker        None, or ("circle", colour) or ("brackets", colour) to be drawn round the
#                 icon (see drawMarker)
# The shape's own colour is used for the outer circle, the compass ring, the sweep,
# the range and the markers.
#
# Markers are fixed places drawn under the blips, such as an airport. Each is a
# tuple of 3 values: (bearing_deg, distance, label), where the label is the
# short text drawn next to it.
#
# Lines are straight lines drawn to scale, such as runways. Each is a tuple of 4 values:
# (bearing_deg1, distance1, bearing_deg2, distance2), for the two ends.
class Radar(LcarsShape):

    def __init__(self, surface, x, y, size, colour, rangeMax, ringStep, units="",
                 blips=None, markers=None, lines=None):

        super().__init__(surface, x, y, size, size, colour)
        self._rangeMax = rangeMax
        self._ringStep = ringStep
        self._units = units
        self._radius = size // 2 - RADAR_MARGIN
        self._blips = []
        self._markers = []
        self._lines = []
        self._still = pygame.Surface((size, size), 0, surface)     # the things that don't move
        self._stillNeedsDrawing = True
        self._glow = None                                           # the sweep's glow, made along with _still
        self.blips = blips
        self.markers = markers
        self.lines = lines


    # Extends the inherited setter: the picture of what doesn't move uses the colour
    @LcarsShape.colour.setter
    def colour(self, value):
        self._colour = value
        self._stillNeedsDrawing = True


    @property
    def blips(self):
        return self._blips

    @blips.setter
    def blips(self, value):
        self._blips = list(value) if value else []


    @property
    def markers(self):
        return self._markers

    @markers.setter
    def markers(self, value):
        self._markers = list(value) if value else []
        self._stillNeedsDrawing = True


    @property
    def lines(self):
        return self._lines

    @lines.setter
    def lines(self, value):
        self._lines = list(value) if value else []
        self._stillNeedsDrawing = True


    # Time-driven (the sweep), so this redraws every frame instead of using _needsUpdate.
    def update(self):
        self.draw()


    def draw(self):
        self._needsUpdate = False

        if self._stillNeedsDrawing:
            self.drawStill()

        centreX = self._x + self._w // 2
        centreY = self._y + self._h // 2
        radius = self._radius
        font = fonts.fontFor(fonts.TextSize.XS)

        # The bearing of the sweep line: it goes clockwise, once round every RADAR_SWEEP_SECONDS
        sweep = time.perf_counter() % RADAR_SWEEP_SECONDS / RADAR_SWEEP_SECONDS * 360

        # Copying the picture over the last frame also clears it
        self._surface.blit(self._still, (self._x, self._y))
        self.drawSweep(centreX, centreY, sweep)

        # The trails, drawn first so that no icon is covered by one
        for bearing, distance, heading, size, colour, label, trail, kind, marker in self._blips:
            self.drawTrail(centreX, centreY, radius, trail, (bearing, distance), colour)

        # The blips, biggest first so that a small icon is never hidden under a big one
        spin = time.perf_counter() * HELICOPTER_SPIN
        for bearing, distance, heading, size, colour, label, trail, kind, marker in sorted(self._blips, key=operator.itemgetter(3), reverse=True):
            x, y = radarPosition(centreX, centreY, radius, self._rangeMax, bearing, distance)
            drawAircraftIcon(self._surface, x, y, size, heading, flareColour(colour, bearing, sweep), kind, spin)

            if marker:
                drawMarker(self._surface, round(x), round(y), round(size * iconScale(kind)) + RADAR_MARKER_GAP, marker)

        # The labels of the blips that have one (the number linking it to the list),
        # drawn last so that no icon covers them
        for bearing, distance, heading, size, colour, label, trail, kind, marker in self._blips:
            if label:
                x, y = radarPosition(centreX, centreY, radius, self._rangeMax, bearing, distance)
                img = font.render(label, True, Colours.WHITE)
                self._surface.blit(img, (x + size * iconScale(kind) + RADAR_LABEL_GAP, y - img.get_height() // 2))


    # Draw everything that doesn't move into the picture that is copied in each frame
    def drawStill(self):
        self._stillNeedsDrawing = False

        surface = self._still
        centre = self._w // 2
        radius = self._radius
        font = fonts.fontFor(fonts.TextSize.XS)

        surface.fill(Colours.BACKGROUND)
        pygame.draw.circle(surface, Colours.DARK_GREY, (centre, centre), radius)

        # Rings inside the circle, and a cross through the centre
        ring = self._ringStep
        while ring < self._rangeMax:
            pygame.draw.circle(surface, Colours.LIGHT_GREY, (centre, centre),
                               round(radius * ring / self._rangeMax), width=1)
            ring += self._ringStep

        pygame.draw.line(surface, Colours.LIGHT_GREY, (centre, centre - radius), (centre, centre + radius))
        pygame.draw.line(surface, Colours.LIGHT_GREY, (centre - radius, centre), (centre + radius, centre))

        # The outer circle and the centre
        pygame.draw.circle(surface, self._colour, (centre, centre), radius, width=2)
        pygame.draw.circle(surface, self._colour, (centre, centre), 3)

        self.drawCompassRing(surface, centre, radius)

        # The range of the outer circle, just outside the ring at its bottom right
        img = font.render(f"{self._rangeMax:g} {self._units}".strip(), True, self._colour)
        corner = radius * math.sqrt(0.5)        # how far right and down the ring is at 45 degrees
        surface.blit(img, (centre + corner + 4, centre + corner + 4))

        # The lines, drawn to scale
        for bearing1, distance1, bearing2, distance2 in self._lines:
            start = radarPosition(centre, centre, radius, self._rangeMax, bearing1, distance1)
            end = radarPosition(centre, centre, radius, self._rangeMax, bearing2, distance2)
            pygame.draw.line(surface, Colours.WHITE, start, end, 2)

        # The markers: a label just below and to the right of the place
        for bearing, distance, label in self._markers:
            x, y = radarPosition(centre, centre, radius, self._rangeMax, bearing, distance)
            surface.blit(font.render(label, True, self._colour), (x + 10, y))

        self._glow = makeSweepGlow(radius, self._colour)


    # The ring of ticks round the outside of the circle (a tick every RADAR_TICK_DEGREES, a
    # longer one every RADAR_LONG_TICK_DEGREES) with the N, E, S and W on tabs at the four points
    def drawCompassRing(self, surface, centre, radius):
        font = fonts.fontFor(fonts.TextSize.XS)
        faint = mixColours(self._colour, Colours.BACKGROUND, 0.45)

        for degrees in range(0, 360, RADAR_TICK_DEGREES):
            if degrees % 90 == 0:
                continue                            # the tabs are there

            if degrees % RADAR_LONG_TICK_DEGREES == 0:
                length, colour = 9, self._colour
            else:
                length, colour = 5, faint

            # Distance 1 of a range of 1 is the whole radius, so these are points at radius + 3 and beyond
            start = radarPosition(centre, centre, radius + 3, 1, degrees, 1)
            end = radarPosition(centre, centre, radius + 3 + length, 1, degrees, 1)
            pygame.draw.line(surface, colour, start, end)

        for letter, dx, dy in (("N", 0, -1), ("E", 1, 0), ("S", 0, 1), ("W", -1, 0)):
            tab = pygame.Rect(0, 0, RADAR_TAB_SIZE, RADAR_TAB_SIZE)
            tab.center = (centre + dx * (radius + RADAR_MARGIN // 2), centre + dy * (radius + RADAR_MARGIN // 2))
            pygame.draw.rect(surface, self._colour, tab, border_radius=4)

            # The letter is centred on its ink, not on its picture, which has space above and below
            img = font.render(letter, True, textColourFor(self._colour))
            ink = img.get_bounding_rect()
            surface.blit(img, (tab.centerx - ink.centerx, tab.centery - ink.centery))


    # The sweep line, and the glow behind it. The glow is turned about its tip, which is
    # in the bottom right corner of its picture, to point the same way as the line.
    def drawSweep(self, centreX, centreY, bearing):
        width, height = self._glow.get_size()
        turned = pygame.transform.rotate(self._glow, -bearing)      # pygame turns pictures anticlockwise

        # The middle of the glow's picture is this far from the tip (up and to the left).
        # Turned clockwise by the bearing, that is where the middle of the turned picture goes.
        angle = math.radians(bearing)
        dx = 0.5 - width / 2
        dy = 0.5 - height / 2
        middleX = centreX + dx * math.cos(angle) - dy * math.sin(angle)
        middleY = centreY + dx * math.sin(angle) + dy * math.cos(angle)
        self._surface.blit(turned, turned.get_rect(center=(round(middleX), round(middleY))))

        end = radarPosition(centreX, centreY, self._radius, 1, bearing, 1)
        pygame.draw.line(self._surface, self._colour, (centreX, centreY), end, 2)


    # A line through the places an aircraft has been, ending where it is now (now is
    # a (bearing, distance) pair). It fades away towards the oldest end.
    def drawTrail(self, centreX, centreY, radius, trail, now, colour):
        points = list(trail) + [now]

        if len(points) < 2:
            return

        positions = [radarPosition(centreX, centreY, radius, self._rangeMax, bearing, distance)
                     for bearing, distance in points]

        for i in range(len(positions) - 1):
            fade = (i + 1) / (len(positions) - 1)
            segment = mixColours(Colours.DARK_GREY, colour, fade)
            pygame.draw.line(self._surface, segment, positions[i], positions[i + 1], 2)


# The icon of one aircraft in a list, pointing up, in the box it is given: the shape and size
# of its kind (see drawAircraftIcon), with a marker (see drawMarker) round it if there is one.
# It is only drawn when visible, so a row with no aircraft shows nothing.
class AircraftIcon(LcarsShape):

    def __init__(self, surface, x, y, w, h, colour=None):
        super().__init__(surface, x, y, w, h, colour)
        self._kind = None
        self._marker = None
        self._visible = False


    @property
    def kind(self):
        return self._kind

    @kind.setter
    def kind(self, value):
        if value != self._kind:
            self._kind = value
            self._needsUpdate = True


    @property
    def marker(self):
        return self._marker

    @marker.setter
    def marker(self, value):
        if value != self._marker:
            self._marker = value
            self._needsUpdate = True


    @property
    def visible(self):
        return self._visible

    @visible.setter
    def visible(self, value):
        if value != self._visible:
            self._visible = value
            self._needsUpdate = True


    def draw(self):
        self._needsUpdate = False
        pygame.draw.rect(self._surface, Colours.BACKGROUND, (self._x, self._y, self._w, self._h))

        if not self._visible:
            return

        # The size of an ordinary aircraft is set so that the biggest kind just fits
        centreX = self._x + self._w // 2
        centreY = self._y + self._h // 2
        half = min(self._w, self._h) // 2
        size = (half - 2) / max(ICON_SCALES.values())

        drawAircraftIcon(self._surface, centreX, centreY, size, 0, self._colour, self._kind)

        if self._marker:
            drawMarker(self._surface, centreX, centreY, half - 2, self._marker)    # its lines are 2 thick, so this keeps them inside the box



class Chiclets(LcarsShape):
    
    def __init__(self, surface, x, y, w, h, colour=None, count=8, gap=4, direction=Direction.VERTICAL):

        assert isinstance(direction, Direction), "Invalid direction argument"

        super().__init__(surface, x, y, w, h, colour)
        self._count = count
        self._gap = gap
        self._direction = direction


    def draw(self):
        
        self._needsUpdate = False

        if self._direction==Direction.VERTICAL:
            seg_h = (self._h - self._gap * (self._count - 1)) / self._count
            for i in range(self._count):
                y0 = round(self._y + i * (seg_h + self._gap))
                y1 = round(self._y + i * (seg_h + self._gap) + seg_h)
                r = pygame.Rect(self._x, y0, self._w, y1 - y0)
                pygame.draw.rect(self._surface, self._colour, r)
                
        else:  # Horizontal
            seg_w = (self._w - self._gap * (self._count - 1)) / self._count
            for i in range(self._count):
                x0 = round(self._x + i * (seg_w + self._gap))
                x1 = round(self._x + i * (seg_w + self._gap) + seg_w)
                r = pygame.Rect(x0, self._y, x1 - x0, self._h)
                pygame.draw.rect(self._surface, self._colour, r)



# A level meter - a column of fixed size segments, lit from the bottom up
# to `level`. The unlit ones are still drawn, dimmed, so the column keeps
# its shape and nothing is left behind when the level drops.
# With direction=Direction.HORIZONTAL it is a row of segments, lit from the left.
class Meter(LcarsShape):

    def __init__(self, surface, x, y, w, h, colour=None, count=8, gap=6, level=None,
                 direction=Direction.VERTICAL):

        assert isinstance(direction, Direction), "Invalid direction argument"

        super().__init__(surface, x, y, w, h, colour)
        self._count = count
        self._gap = gap
        self._direction = direction
        self._dim = dimColour(self._colour)

        if level is None:
            self._level = count // 2
        else:
            self._level = level


    # Extends the inherited setter so the unlit segments stay in step
    # with the lit ones if something changes the colour.
    @LcarsShape.colour.setter
    def colour(self, value):
        self._colour = value
        self._dim = dimColour(value)
        self._needsUpdate = True


    @property
    def count(self):
        return self._count


    @property
    def level(self):
        return self._level

    # Clamped, so callers can just add and subtract without checking
    @level.setter
    def level(self, value):
        value = max(0, min(self._count, value))

        if value != self._level:
            self._level = value
            self._needsUpdate = True


    def draw(self):

        self._needsUpdate = False

        if self._direction == Direction.HORIZONTAL:
            seg_w = (self._w - self._gap * (self._count - 1)) / self._count

            for i in range(self._count):
                x0 = round(self._x + i * (seg_w + self._gap))
                x1 = round(self._x + i * (seg_w + self._gap) + seg_w)

                # Segments light from the left
                lit = i < self._level

                pygame.draw.rect(self._surface, self._colour if lit else self._dim,
                                 pygame.Rect(x0, self._y, x1 - x0, self._h))

            return

        seg_h = (self._h - self._gap * (self._count - 1)) / self._count

        for i in range(self._count):
            y0 = round(self._y + i * (seg_h + self._gap))
            y1 = round(self._y + i * (seg_h + self._gap) + seg_h)

            # Segments light from the bottom up
            lit = i >= self._count - self._level

            pygame.draw.rect(self._surface, self._colour if lit else self._dim,
                             pygame.Rect(self._x, y0, self._w, y1 - y0))



# A block of numbers that keep changing, like the data on a starship console, in `columns`
# columns and `rows` rows of `digits` digits each. A few of the numbers change every
# CASCADE_INTERVAL seconds, and each is either in the full colour or a dimmer one (it is
# chosen again whenever the number changes), which keeps the block shimmering. Only the
# numbers that change are redrawn.
class Cascade(LcarsShape):

    def __init__(self, surface, x, y, w, h, colour=None, columns=3, rows=10, digits=5,
                 textSize=fonts.TextSize.XS):

        assert isinstance(textSize, fonts.TextSize), "Invalid textSize argument"

        super().__init__(surface, x, y, w, h, colour)
        self._columns = columns
        self._rows = rows
        self._digits = digits
        self._textSize = textSize
        self._dim = mixColours(self._colour, Colours.BACKGROUND, 0.55)
        self._cells = [self.newCell() for _ in range(columns * rows)]       # (text, bright) of each number, row by row
        self._changeAt = time.perf_counter()


    # A new random number, and whether it is to be in the full colour
    def newCell(self):
        return ("%0*d" % (self._digits, random.randrange(10 ** self._digits)), random.random() < 0.35)


    # Time-driven, so this changes the numbers every frame it is due instead of using _needsUpdate
    def update(self):
        if self._needsUpdate:
            self.draw()

        now = time.perf_counter()
        if now < self._changeAt:
            return

        self._changeAt = now + CASCADE_INTERVAL

        for _ in range(CASCADE_CHANGES):
            index = random.randrange(len(self._cells))
            self._cells[index] = self.newCell()
            self.drawCell(index)


    def draw(self):
        self._needsUpdate = False

        for index in range(len(self._cells)):
            self.drawCell(index)


    # Draw one number, clearing the one it replaces
    def drawCell(self, index):
        row, column = divmod(index, self._columns)
        cellW = self._w // self._columns
        cellH = self._h // self._rows
        x = self._x + column * cellW
        y = self._y + row * cellH

        text, bright = self._cells[index]
        img = fonts.fontFor(self._textSize).render(text, True, self._colour if bright else self._dim)
        capTop, capHeight = fonts.capMetricsFor(self._textSize)

        pygame.draw.rect(self._surface, Colours.BACKGROUND, (x, y, cellW, cellH))
        self._surface.blit(img, (x + CASCADE_PAD, y + (cellH - capHeight) // 2 - capTop))



# Where a light that bounces back and forth along `count` places is after `step` steps
# (0, 1, ... count-1, count-2, ... 1, 0, 1, ...), and the way it has just come: 1 if
# it moved up the places to get there, -1 if it moved down.
def bouncePosition(step, count):
    cycle = 2 * (count - 1)
    place = step % cycle

    if place == 0:
        return 0, -1

    if place < count:
        return place, 1

    return cycle - place, -1



# The colour of a segment that is `behind` places behind the light (0 is the light itself,
# negative is ahead of it): the light is nearly white, then the glow fades away behind it.
def searchSegmentColour(colour, behind):
    unlit = mixColours(colour, Colours.BACKGROUND, SEARCH_UNLIT)

    if behind < 0 or behind >= SEARCH_TRAIL:
        return unlit

    if behind == 0:
        return mixColours(colour, Colours.WHITE, SEARCH_HEAD_WHITE)

    return mixColours(colour, unlit, behind / SEARCH_TRAIL)



# What to show instead of a list that has nothing in it: a title, SCANNING with its dots
# coming and going, and rows of segments with a light bouncing along each at its own
# speed, leaving a glow behind. Rows alternate between colour and colour2.
# Set `active` to show it. When it is turned off the area is cleared at once, so
# whatever draws there next is not drawn over. Only the rows whose light has moved
# on are redrawn.
class Searching(LcarsShape):

    def __init__(self, surface, x, y, w, h, colour=None, colour2=None, title="No contacts"):
        super().__init__(surface, x, y, w, h, colour)
        self._colour2 = colour2 if colour2 else self._colour
        self._title = title
        self._active = False
        self._start = time.perf_counter()
        self._dots = -1                                     # how many dots are showing, -1 if none drawn yet
        self._rowSteps = [-1] * SEARCH_ROWS                 # the step each row was last drawn at
        self._rowSpeeds = [random.uniform(SEARCH_MIN_SPEED, SEARCH_MAX_SPEED) for _ in range(SEARCH_ROWS)]
        self._rowOffsets = [random.randrange(2 * (SEARCH_SEGMENTS - 1)) for _ in range(SEARCH_ROWS)]


    @property
    def active(self):
        return self._active

    @active.setter
    def active(self, active):
        if active == self._active:
            return

        self._active = active

        if active:
            self._needsUpdate = True
        else:
            pygame.draw.rect(self._surface, Colours.BACKGROUND, (self._x, self._y, self._w, self._h))


    @property
    def title(self):
        return self._title

    @title.setter
    def title(self, title):
        if title != self._title:
            self._title = title
            self._needsUpdate = True


    # Time-driven, so this moves the lights on every frame they are due
    def update(self):
        if not self._active:
            return

        if self._needsUpdate:
            self.draw()
        else:
            self.drawSubtitle()
            self.drawRows()


    # Everything: clear the area, then draw all of it afresh
    def draw(self):
        self._needsUpdate = False
        self._dots = -1
        self._rowSteps = [-1] * SEARCH_ROWS

        pygame.draw.rect(self._surface, Colours.BACKGROUND, (self._x, self._y, self._w, self._h))

        self.drawText(self._title.upper(), fonts.TextSize.MEDIUM, self._colour, self._y, SEARCH_TITLE_HEIGHT)
        self.drawSubtitle()
        self.drawRows()


    # Text on the left of the area, centred in a band of this height starting at y
    def drawText(self, text, textSize, colour, y, height):
        img = fonts.fontFor(textSize).render(text, True, colour)
        capTop, capHeight = fonts.capMetricsFor(textSize)
        self._surface.blit(img, (self._x, y + (height - capHeight) // 2 - capTop))


    # SCANNING and its dots, drawn again only when the number of dots changes
    def drawSubtitle(self):
        dots = int((time.perf_counter() - self._start) / SEARCH_DOT_SECONDS) % 4

        if dots == self._dots:
            return

        self._dots = dots
        top = self._y + SEARCH_TITLE_HEIGHT
        pygame.draw.rect(self._surface, Colours.BACKGROUND, (self._x, top, self._w, SEARCH_SUBTITLE_HEIGHT))
        self.drawText("SCANNING" + "." * dots, fonts.TextSize.SMALL, self._colour2, top, SEARCH_SUBTITLE_HEIGHT)


    # The rows whose light has moved on since they were drawn
    def drawRows(self):
        elapsed = time.perf_counter() - self._start

        for row in range(SEARCH_ROWS):
            step = int(elapsed * self._rowSpeeds[row]) + self._rowOffsets[row]

            if step != self._rowSteps[row]:
                self._rowSteps[row] = step
                self.drawRow(row, step)


    def drawRow(self, row, step):
        head, direction = bouncePosition(step, SEARCH_SEGMENTS)
        colour = self._colour if row % 2 == 0 else self._colour2

        gridTop = self._y + SEARCH_TITLE_HEIGHT + SEARCH_SUBTITLE_HEIGHT
        rowHeight = (self._h - SEARCH_TITLE_HEIGHT - SEARCH_SUBTITLE_HEIGHT) // SEARCH_ROWS
        segmentWidth = (self._w - (SEARCH_SEGMENTS - 1) * SEARCH_GAP) // SEARCH_SEGMENTS
        top = gridTop + row * rowHeight

        for segment in range(SEARCH_SEGMENTS):
            behind = (head - segment) * direction
            left = self._x + segment * (segmentWidth + SEARCH_GAP)
            pygame.draw.rect(self._surface, searchSegmentColour(colour, behind),
                             (left, top, segmentWidth, rowHeight - SEARCH_GAP))



# A panel that jumps up in the middle of the screen to warn of something, flashing between
# two colours. It is not one of the shapes drawn on the background: draw() is called every
# frame on the screen itself, after the background has been copied there, so nothing has
# to be restored when it goes away.
#
#   popup.show("EMERGENCY SQUAWK", ("THY9GV", "7700 EMERGENCY", "7,800 ft  280 kt"), 15)
#   popup.draw(screen)          # every frame; draws nothing once the time is up
class Popup:

    def __init__(self, centreX, centreY):
        self._centre = (centreX, centreY)
        self._until = 0
        self._titles = None             # the title as drawn on each of the two colours
        self._lines = None              # the three lines of text as images: white, flashing, small
        self._rect = None


    # Show it for this many seconds. The title and the three lines are the text; the
    # middle line flashes with the frame.
    def show(self, title, lines, seconds):
        colours = (Colours.RED, Colours.WHITE)
        self._until = time.perf_counter() + seconds
        self._titles = [fonts.fontFor(fonts.TextSize.LARGE).render(title, True, textColourFor(colour)) for colour in colours]

        big, middle, small = lines
        self._lines = (fonts.fontFor(fonts.TextSize.XL).render(big, True, Colours.WHITE),
                       [fonts.fontFor(fonts.TextSize.LARGE).render(middle, True, colour) for colour in colours],
                       fonts.fontFor(fonts.TextSize.MEDIUM).render(small, True, Colours.WHITE))

        height = 2 * POPUP_FRAME + POPUP_TITLE_HEIGHT + sum(POPUP_BAND_HEIGHTS) + POPUP_PAD
        self._rect = pygame.Rect(0, 0, POPUP_WIDTH, height)
        self._rect.center = self._centre


    @property
    def visible(self):
        return time.perf_counter() < self._until


    def hide(self):
        self._until = 0


    def draw(self, surface):
        if not self.visible:
            return

        flash = 0 if int(time.perf_counter() * POPUP_FLASH_HZ * 2) % 2 == 0 else 1
        colour = (Colours.RED, Colours.WHITE)[flash]
        rect = self._rect

        pygame.draw.rect(surface, Colours.BACKGROUND, rect, border_radius=POPUP_RADIUS)
        pygame.draw.rect(surface, colour, rect, width=POPUP_FRAME, border_radius=POPUP_RADIUS)

        # The title on a bar across the top, inside the frame
        bar = pygame.Rect(rect.x + POPUP_FRAME, rect.y + POPUP_FRAME, rect.width - 2 * POPUP_FRAME, POPUP_TITLE_HEIGHT)
        pygame.draw.rect(surface, colour, bar, border_top_left_radius=POPUP_RADIUS - POPUP_FRAME,
                         border_top_right_radius=POPUP_RADIUS - POPUP_FRAME)
        self.blitCentred(surface, self._titles[flash], fonts.TextSize.LARGE, rect.x + POPUP_PAD, bar.y, POPUP_TITLE_HEIGHT)

        # The three lines, each centred in its own band of height
        big, middle, small = self._lines
        y = bar.bottom
        for image, size, band in ((big, fonts.TextSize.XL, POPUP_BAND_HEIGHTS[0]),
                                  (middle[flash], fonts.TextSize.LARGE, POPUP_BAND_HEIGHTS[1]),
                                  (small, fonts.TextSize.MEDIUM, POPUP_BAND_HEIGHTS[2])):
            self.blitCentred(surface, image, size, rect.x + POPUP_PAD, y, band)
            y += band


    # Draw an image of text of this size at x, so that its capital letters are centred in a
    # band of this height starting at y
    def blitCentred(self, surface, image, textSize, x, y, height):
        capTop, capHeight = fonts.capMetricsFor(textSize)
        surface.blit(image, (x, y + (height - capHeight) // 2 - capTop))



# Cycles through a list of strings in a single-line box, one at a time.
# Any string too wide for the box scrolls; anything that fits is just held.
# message() shows a string once, straight away, and then the list carries on.
class TextScroller(LcarsShape):

    def __init__(self, surface, x, y, w, h, colour=None, texts=None, textSize=fonts.TextSize.MEDIUM):

        assert isinstance(textSize, fonts.TextSize), "Invalid textSize argument"

        super().__init__(surface, x, y, w, h, colour)
        self._textSize = textSize
        self._width = w - 2 * SCROLL_PAD
        self._texts = []
        self._messages = []         # strings to show once, the one being shown first
        self._index = 0
        self._img = None
        self._scrollX = 0.0
        self._start = time.perf_counter()
        self.texts = texts


    @property
    def texts(self):
        return self._texts

    # Changing the texts does not restart the scroller. The current position
    # in the list and the current scroll/hold timing carry on, and the string
    # being shown is simply re-rendered from the new list. It only starts from
    # the beginning if the list was empty or the position is no longer valid.
    @texts.setter
    def texts(self, value):
        newTexts = list(value) if value else []

        # Nothing changed, so there is nothing to do
        if newTexts == self._texts:
            return

        wasEmpty = not self._texts
        self._texts = newTexts

        if not newTexts:
            self._img = None
            self._index = 0
            return

        if wasEmpty or self._index >= len(newTexts):
            self._index = 0
            self._prepare()     # fresh start: resets the timer and renders
        else:
            self._render()      # keep _start and _index, just re-render


    # Show this string once, and then carry on with the list from where it had got to. It
    # is shown straight away, or after the messages already waiting if there are any (at
    # most SCROLL_MAX_MESSAGES can wait; a message that comes when they are all taken is dropped).
    def message(self, text):
        if len(self._messages) >= SCROLL_MAX_MESSAGES:
            return

        self._messages.append(text)

        if len(self._messages) == 1:
            self._prepare()


    # The string that is on show: the first message if there is one, otherwise the list's
    def _current(self):
        if self._messages:
            return self._messages[0]

        return self._texts[self._index]


    # Render the current string and work out how long it stays on screen:
    # a hold, then (if it overflows) the scroll itself plus a hold at the end.
    def _prepare(self):
        self._scrollX = 0.0
        self._start = time.perf_counter()

        if not self._texts and not self._messages:
            self._img = None
            return

        self._render()


    def _render(self):
        self._renderColour = textColourFor(self._colour)
        self._img = fonts.fontFor(self._textSize).render(self._current().upper(), True, self._renderColour)
        self._overflow = max(0, self._img.get_width() - self._width)
        self._duration = SCROLL_HOLD
        if self._overflow:
            self._duration += self._overflow / SCROLL_SPEED + SCROLL_HOLD


    # Time-driven, so this redraws every frame instead of using _needsUpdate.
    def update(self):
        if not self._img:
            return

        elapsed = time.perf_counter() - self._start
        if elapsed >= self._duration:
            if self._messages:
                self._messages.pop(0)           # it has had its turn
            else:
                self._index = (self._index + 1) % len(self._texts)

            self._prepare()
            elapsed = 0.0

        # The colour can change under us - a Twinkler sets it - so the text
        # may need re-rendering to stay readable.
        if self._renderColour != textColourFor(self._colour):
            self._render()

        self._scrollX = min(max(0.0, (elapsed - SCROLL_HOLD) * SCROLL_SPEED), self._overflow)
        self.draw()


    def draw(self):

        pygame.draw.rect(self._surface, self._colour, (self._x, self._y, self._w, self._h))

        if not self._img:
            return

        # Clip so a mid-scroll string can't spill outside the box.
        previousClip = self._surface.get_clip()
        self._surface.set_clip((self._x + SCROLL_PAD, self._y, self._width, self._h))

        capTop, capHeight = fonts.capMetricsFor(self._textSize)
        self._surface.blit(self._img, (self._x + SCROLL_PAD - self._scrollX,
                                       self._y + (self._h - capHeight) // 2 - capTop))

        self._surface.set_clip(previousClip)



# A continuous news-ticker style scroll, with a bullet between each string.
# The whole list is rendered as one strip and repeated end to end, so it
# scrolls without a gap or a jump when it wraps around.
class Ticker(LcarsShape):

    def __init__(self, surface, x, y, w, h, colour=None, texts=None,
                 textSize=fonts.TextSize.MEDIUM, textColour=None):

        assert isinstance(textSize, fonts.TextSize), "Invalid textSize argument"

        super().__init__(surface, x, y, w, h, colour)
        self._textSize = textSize
        self._textColour = textColour
        self._offset = 0.0                      # scroll position in pixels
        self._lastTime = time.perf_counter()
        self._texts = []
        self._img = None
        self._stripWidth = 0
        self.texts = texts


    @property
    def texts(self):
        return self._texts

    @texts.setter
    def texts(self, value):
        newTexts = list(value) if value else []

        # Nothing changed, so there is nothing to re-render
        if newTexts == self._texts:
            return

        # The scroll position is deliberately kept, so new text carries on
        # from where the old text had got to instead of jumping back.
        self._texts = newTexts
        self._render()


    # Follows the shape's colour unless one has been set explicitly.
    @property
    def textColour(self):
        if self._textColour:
            return self._textColour

        return textColourFor(self._colour)

    @textColour.setter
    def textColour(self, value):
        self._textColour = value
        self._render()


    def _render(self):
        if not self._texts:
            self._img = None
            self._stripWidth = 0
            self._offset = 0.0
            return

        # The trailing separator is what joins the end of the strip back
        # onto its own beginning as it repeats.
        strip = TICKER_SEPARATOR.join(self._texts).upper() + TICKER_SEPARATOR

        self._renderColour = self.textColour
        self._img = fonts.fontFor(self._textSize).render(strip, True, self._renderColour)
        self._stripWidth = self._img.get_width()

        # The new strip may be shorter than the old one
        self._offset %= self._stripWidth


    # Time-driven, so this redraws every frame instead of using _needsUpdate.
    def update(self):
        now = time.perf_counter()
        elapsed = now - self._lastTime
        self._lastTime = now

        if not self._img:
            return

        if self._renderColour != self.textColour:
            self._render()

        self._offset = (self._offset + elapsed * TICKER_SPEED) % self._stripWidth

        self.draw()


    def draw(self):

        self._needsUpdate = False
        pygame.draw.rect(self._surface, self._colour, (self._x, self._y, self._w, self._h))

        if not self._img or not self._stripWidth:
            return

        previousClip = self._surface.get_clip()
        self._surface.set_clip((self._x, self._y, self._w, self._h))

        capTop, capHeight = fonts.capMetricsFor(self._textSize)
        y = self._y + (self._h - capHeight) // 2 - capTop

        # Repeat the strip until the box is covered
        x = self._x - self._offset
        while x < self._x + self._w:
            self._surface.blit(self._img, (x, y))
            x += self._stripWidth

        self._surface.set_clip(previousClip)
 
 

# Wraps any shape and flips its colour between two colours. The wrapped
# shape needs no changes - it just sees its colour property being set.
# The shape stays accessible as .shape:
#   twinkler = Twinkler(Pill(background, 10, 10, 200, 40, Colours.RED), Colours.ORANGE)
#   twinkler.shape.text = "STATUS OK"
class Twinkler:

    def __init__(self, shape, colour2=None, rate=TwinkleRate.MEDIUM_RANDOM):

        assert isinstance(rate, TwinkleRate), "Invalid rate argument"

        self.shape = shape
        self._colour1 = shape.colour
        self._rate = rate
        self._showSecondColour = False

        if colour2:
            self._colour2 = colour2
        else:
            self._colour2 = random.choice(Colours.LCARS_COLOURS)

        self._scheduleNext()


    @property
    def rate(self):
        return self._rate

    @rate.setter
    def rate(self, value):
        assert isinstance(value, TwinkleRate), "Invalid rate argument"
        self._rate = value
        self._scheduleNext()


    def _scheduleNext(self):
        period = self._rate.period

        if self._rate.isRandom:
            period = random.uniform(period * (1 - TWINKLE_SPREAD), period * (1 + TWINKLE_SPREAD))

        self._switchAt = time.perf_counter() + period


    def update(self):
        if time.perf_counter() >= self._switchAt:
            self._showSecondColour = not self._showSecondColour
            self.shape.colour = self._colour2 if self._showSecondColour else self._colour1
            self._scheduleNext()

        self.shape.update()


# (x, y) is the TOP-LEFT corner of the elbow's bounding box.
class ElbowTopLeft(LcarsShape):
    
    def __init__(self, surface, x, y, w, h, colour=None, arm_w=200, arm_h=200):

        super().__init__(surface, x, y, w, h, colour)
        self._arm_w = arm_w
        self._arm_h = arm_h
        

    def draw(self):
        
        self._needsUpdate = False

        # horizontal arm
        pygame.draw.rect(self._surface, self._colour, pygame.Rect(self._x, self._y, self._w, self._arm_h))

        # vertical arm
        pygame.draw.rect(self._surface, self._colour, pygame.Rect(self._x, self._y, self._arm_w, self._h))

        # outer corner
        radius = min(self._arm_w, self._arm_h, 60)
        pygame.draw.rect(self._surface, Colours.BACKGROUND, 
                            (self._x, self._y, radius, radius))
        pygame.draw.circle(self._surface, self._colour, 
                            (self._x+radius, self._y+radius), radius)        

        # inner corner
        pygame.draw.rect(self._surface, self._colour, 
                            (self._x + self._arm_w, self._y + self._arm_h, radius, radius))
        pygame.draw.circle(self._surface, Colours.BACKGROUND, 
                            (self._x + radius + self._arm_w, self._y + radius + self._arm_h), radius)        
        


# (x, y) is the TOP-RIGHT corner of the elbow's bounding box.
class ElbowTopRight(LcarsShape):
    
    def __init__(self, surface, x, y, w, h, colour=None, arm_w=200, arm_h=200):

        super().__init__(surface, x, y, w, h, colour)
        self._arm_w = arm_w
        self._arm_h = arm_h
        

    def draw(self):
        
        self._needsUpdate = False

        # horizontal arm
        pygame.draw.rect(self._surface, self._colour, pygame.Rect(self._x-self._w, self._y, self._w, self._arm_h))

        # vertical arm
        pygame.draw.rect(self._surface, self._colour, pygame.Rect(self._x-self._arm_w, self._y, self._arm_w, self._h))

        # outer corner
        radius = min(self._arm_w, self._arm_h, 60)
        pygame.draw.rect(self._surface, Colours.BACKGROUND, (self._x-radius, self._y, radius, radius))
        pygame.draw.circle(self._surface, self._colour, (self._x-radius, self._y+radius), radius)        

        # inner corner
        pygame.draw.rect(self._surface, self._colour, (self._x - self._arm_w - radius, self._y + self._arm_h, radius, radius))
        pygame.draw.circle(self._surface, Colours.BACKGROUND, (self._x - self._arm_w - radius , self._y + radius + self._arm_h), radius)        
        

# (x, y) is the BOTTOM-LEFT corner of the elbow's bounding box.
class ElbowBottomLeft(LcarsShape):
    
    def __init__(self, surface, x, y, w, h, colour=None, arm_w=200, arm_h=200):

        super().__init__(surface, x, y, w, h, colour)
        self._arm_w = arm_w
        self._arm_h = arm_h
        

    def draw(self):
        
        self._needsUpdate = False
        
        # horizontal arm
        pygame.draw.rect(self._surface, self._colour, pygame.Rect(self._x, self._y-self._arm_h, self._w, self._arm_h))

        # vertical arm
        pygame.draw.rect(self._surface, self._colour, pygame.Rect(self._x, self._y-self._h, self._arm_w, self._h))

        # outer corner
        radius = min(self._arm_w, self._arm_h, 60)
        pygame.draw.rect(self._surface, Colours.BACKGROUND, (self._x, self._y-radius, radius, radius))
        pygame.draw.circle(self._surface, self._colour, (self._x+radius, self._y-radius), radius)        

        # inner corner
        pygame.draw.rect(self._surface, self._colour, (self._x + self._arm_w, self._y - radius - self._arm_h, radius, radius))
        pygame.draw.circle(self._surface, Colours.BACKGROUND, (self._x + radius + self._arm_w, self._y - radius - self._arm_h), radius)        
        



# (x, y) is the BOTTOM-RIGHT corner of the elbow's bounding box.
class ElbowBottomRight(LcarsShape):
    
    def __init__(self, surface, x, y, w, h, colour=None, arm_w=200, arm_h=200):

        super().__init__(surface, x, y, w, h, colour)
        self._arm_w = arm_w
        self._arm_h = arm_h
        

    def draw(self):
        
        self._needsUpdate = False
        
        # horizontal arm
        pygame.draw.rect(self._surface, self._colour, pygame.Rect(self._x-self._w, self._y-self._arm_h, self._w, self._arm_h))

        # vertical arm
        pygame.draw.rect(self._surface, self._colour, pygame.Rect(self._x-self._arm_w, self._y-self._h, self._arm_w, self._h))

        # outer corner
        radius = min(self._arm_w, self._arm_h, 60)
        pygame.draw.rect(self._surface, Colours.BACKGROUND, (self._x-radius, self._y-radius, radius, radius))
        pygame.draw.circle(self._surface, self._colour, (self._x-radius, self._y-radius), radius)        

        # inner corner
        pygame.draw.rect(self._surface, self._colour, 
                            (self._x - self._arm_w - radius, self._y - radius - self._arm_h, radius, radius))
            
        pygame.draw.circle(self._surface, Colours.BACKGROUND, 
                            (self._x - self._arm_w - radius, self._y - radius - self._arm_h), radius)
                            