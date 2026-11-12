"""
calendar_data.py

Holds a copy of the calendar events under common names that don't depend on
the calendar provider. The code that fetches the events (currently Google
Calendar, in lcars_calendar.py) translates the provider's names and formats
into the ones below. Change providers by writing a new translation; nothing
that reads a CalendarData needs to change.

Two classes:

    CalendarEvent    one event
    CalendarData     a list of CalendarEvent plus the time of the last fetch

Every value of a CalendarEvent is a property with a getter and a setter. They
all start as None, meaning "the provider didn't supply it", and are filled in
with the setters. Nothing is checked.

CalendarEvent also has two read-only pieces of display text, built from start
and all_day, for showing the date and the time in separate columns:

    event.date_text(now)    'TODAY', 'TOMORROW' or 'FRI 16 OCT'
    event.time_text         '14:00', or '' (blank) for an all-day event

CalendarData holds the list of events:

    data = CalendarData()
    data.load(events)                   # also sets last_success to the time now

    data.events[0].summary              # list of CalendarEvent
    data.events[0].start                # Unix timestamp
    data.last_success                   # Unix timestamp (float), or None

    event = CalendarEvent()
    event.summary = "Dentist"
    event.start = 1760623200
    event.all_day = False

UNITS (every provider's values are converted to these)
    summary     text, the event title
    start       Unix timestamp, seconds, UTC. An all-day event starts at
                midnight at the start of its day, in this machine's local time.
    all_day     True or False

The data is deep-copied on the way into CalendarData (by load() and by the
setters), so later changes to the objects that were passed in don't alter this
one. The getters return the stored objects themselves (not further copies), so
treat what they return as read-only.
"""

import copy
import datetime
import time


# Convert a start time to a day label, relative to now_ts (both Unix
# timestamps, in seconds): 'TODAY', 'TOMORROW', or for anything further out a
# weekday and date, e.g. 'FRI 16 OCT'. Uses this machine's local time.
# Returns '' (blank) if there is no start time.
def unix_to_day_label(start_ts, now_ts):
    if start_ts is None:
        return ""

    start_date = datetime.datetime.fromtimestamp(start_ts).date()
    today = datetime.datetime.fromtimestamp(now_ts).date()

    days_away = (start_date - today).days
    if days_away == 0:
        return "TODAY"
    if days_away == 1:
        return "TOMORROW"
    return start_date.strftime("%a %d %b").upper()


# Convert a start time to local-time 'HH:MM', e.g. '14:00'.
# Returns '' (blank) if there is no start time.
def unix_to_hhmm(start_ts):
    if start_ts is None:
        return ""
    return datetime.datetime.fromtimestamp(start_ts).strftime("%H:%M")


# One calendar event.
class CalendarEvent:

    def __init__(self):
        self._summary = None
        self._start = None
        self._all_day = None


    # The event title
    @property
    def summary(self):
        return self._summary

    @summary.setter
    def summary(self, value):
        self._summary = value


    # Unix timestamp of the start (an all-day event: local midnight)
    @property
    def start(self):
        return self._start

    @start.setter
    def start(self, value):
        self._start = value


    # True for an all-day event, which has a date but no time
    @property
    def all_day(self):
        return self._all_day

    @all_day.setter
    def all_day(self, value):
        self._all_day = value


    # 'TODAY', 'TOMORROW' or 'FRI 16 OCT', relative to now_ts (a Unix
    # timestamp), or '' (blank) if there is no start. Read-only.
    def date_text(self, now_ts):
        return unix_to_day_label(self._start, now_ts)


    # '14:00', or '' (blank) for an all-day event or if there is no start.
    # Read-only.
    @property
    def time_text(self):
        if self._all_day:
            return ""
        return unix_to_hhmm(self._start)



class CalendarData:

    def __init__(self):
        self._events = []
        self._last_success = None


    # Replace the events with a copy of the new ones, and set last_success to
    # the current time. A missing (None) events becomes an empty list.
    def load(self, events):
        self.events = events
        self.last_success = time.time()


    # The events, soonest first, as a list of CalendarEvent.
    @property
    def events(self):
        return self._events

    @events.setter
    def events(self, value):
        items = list(value) if value else []
        assert all(isinstance(item, CalendarEvent) for item in items), "list of CalendarEvent expected"
        self._events = copy.deepcopy(items)


    # Unix timestamp (float) of the last load(), i.e. the last successful
    # fetch, or None if there has never been one.
    @property
    def last_success(self):
        return self._last_success

    @last_success.setter
    def last_success(self, value):
        self._last_success = value