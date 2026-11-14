"""
lcars_calendar.py

Fetches your next Google Calendar events on a background thread and keeps them
as a CalendarData (see calendar_data.py). This is the only place that knows
about Google Calendar's names and formats: they are translated into the
provider-independent classes here, so changing calendar provider only means
changing this file. No drawing code - display them however you like.

Usage:

    fetcher = CalendarFetcher(max_events=5).start()
    ...
    calendar = fetcher.get_calendar()       # a CalendarData (read-only)
    error = fetcher.get_error()             # str, or None if the last fetch worked
    now = int(time.time())
    for event in calendar.events:
        print(event.date_text(now), event.time_text, event.summary)

    calendar.last_success   # Unix time of the last good fetch, or None if never

ONE-TIME SETUP
--------------
1. pip install --break-system-packages google-api-python-client \\
       google-auth-httplib2 google-auth-oauthlib

2. In Google Cloud Console (console.cloud.google.com):
     - Create a project (or pick an existing one).
     - APIs & Services -> Library -> enable "Google Calendar API".
     - APIs & Services -> OAuth consent screen -> configure it
       ("External", adding yourself as a test user, is fine).
     - APIs & Services -> Credentials -> Create Credentials -> OAuth
       client ID -> "Desktop app".
     - Download the JSON and save it as credentials.json next to this script.

3. Run once on a machine with a browser. It asks you to sign in and approve
   read-only calendar access, then saves token.json. Later runs refresh
   silently.

If credentials are missing or the google packages aren't installed,
get_calendar() has no events and get_error() gives the reason, rather than
anything being raised. Each failure is also printed, with its traceback.
"""

import datetime
import os
import sys
import threading
import traceback

from .calendar_data import CalendarEvent, CalendarData

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

# Next to this script, not in the current directory, so they are found wherever it is started from
CREDENTIALS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "credentials.json")
TOKEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "token.json")
# Its settings are in settings.py (next to lcars.py)
from settings import (
    CALENDAR_ID,
    CALENDAR_MAX_PAGES as MAX_PAGES,
    CALENDAR_DEBUG as DEBUG,
)




def _start_to_unix(start_str, all_day):
    """Google's start value -> Unix timestamp (int). A timed event's ISO
    string carries its own UTC offset, so the result is exact. An all-day
    event is a plain date, which becomes midnight at the start of that day
    in this machine's local time."""
    if all_day:
        d = datetime.date.fromisoformat(start_str)
        return int(datetime.datetime.combine(d, datetime.time.min).timestamp())
    # "Z" -> "+00:00" because fromisoformat rejects "Z" before Python 3.11.
    return int(datetime.datetime.fromisoformat(
        start_str.replace("Z", "+00:00")).timestamp())


# An exception as text that is never blank: 'RefreshError: invalid_scope ...'.
# Some exceptions have no message at all, so the type name always goes first.
def error_text(exc):
    message = str(exc)
    if message:
        return f"{type(exc).__name__}: {message}"
    return type(exc).__name__


# Print a failed fetch with its full traceback. Both go to stderr, which is
# never buffered, so they appear straight away wherever the program is run from.
def report_failure(what, exc):
    print(f"{what} failed: {error_text(exc)}", file=sys.stderr, flush=True)
    traceback.print_exception(type(exc), exc, exc.__traceback__)


class CalendarFetcher:
    """
    Polls Google Calendar for upcoming events on its own daemon thread.
    Never blocks the caller, and on a failed poll keeps the last good
    event list rather than clearing it.
    """

    def __init__(self, poll_seconds=600, max_events=7, days_ahead=14,
                 calendar_id=CALENDAR_ID):
        self.poll_seconds = poll_seconds
        self.max_events = max_events
        self.days_ahead = days_ahead
        self.calendar_id = calendar_id
        self._lock = threading.Lock()
        self._calendar = CalendarData()     # the latest good data; replaced, never changed
        self._error = None                  # str, or None if the last poll worked
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._service = None

    def start(self):
        self._poll_once()  # first fetch synchronously so data is ready
        self._thread.start()
        return self

    def stop(self):
        self._stop.set()

    def _run(self):
        while not self._stop.wait(self.poll_seconds):
            self._poll_once()

    def _get_service(self):
        if self._service is not None:
            return self._service

        # Deferred imports so everything else works without the google packages.
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build

        creds = None
        if os.path.exists(TOKEN_FILE):
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(CREDENTIALS_FILE):
                    raise FileNotFoundError(
                        f"{CREDENTIALS_FILE} not found - see the setup steps "
                        f"in this module's docstring")
                flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
                print("Google needs your approval: opening a browser to sign in "
                      "(this waits until you do)", file=sys.stderr, flush=True)
                creds = flow.run_local_server(port=0)
            with open(TOKEN_FILE, "w") as f:
                f.write(creds.to_json())

        self._service = build("calendar", "v3", credentials=creds)
        return self._service

    # Ask Google for the events, a page at a time. Google's pages can be shorter than
    # max_events even when more events are coming, so keep asking for the next page
    # (page_token) until there are enough events or Google has no more.
    def _fetch_events(self, service):
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        time_min = now_utc.isoformat()
        time_max = (now_utc + datetime.timedelta(days=self.days_ahead)).isoformat()

        events = []
        page_token = None
        pages = 0
        while pages < MAX_PAGES:
            result = service.events().list(
                calendarId=self.calendar_id, timeMin=time_min, timeMax=time_max,
                maxResults=self.max_events, singleEvents=True,
                orderBy="startTime", pageToken=page_token).execute()
            pages += 1

            for item in result.get("items", []):
                start_info = item.get("start", {})
                all_day = "date" in start_info and "dateTime" not in start_info
                start = start_info.get("dateTime", start_info.get("date"))
                if start is None:
                    continue

                event = CalendarEvent()
                event.summary = item.get("summary") or "(no title)"
                event.start = _start_to_unix(start, all_day)
                event.all_day = all_day
                events.append(event)

            page_token = result.get("nextPageToken")
            if page_token is None or len(events) >= self.max_events:
                break

        return events[:self.max_events], pages

    def _poll_once(self):
        try:
            try:
                events, pages = self._fetch_events(self._get_service())
            except OSError:
                # The connection kept open since the last poll (ten minutes ago) has been
                # closed at the other end, by Google or a router, which shows up as an
                # error like SSLEOFError when it is used. A new connection fixes that, so
                # make one and try again, once.
                print("Calendar connection was closed - reconnecting", file=sys.stderr, flush=True)
                self._service = None
                events, pages = self._fetch_events(self._get_service())

            if DEBUG:
                print(f"Calendar: {len(events)} event(s) from {pages} page(s)")

            # A new CalendarData each time, which is never changed once it is
            # published, so readers can hold on to the one they were given.
            calendar = CalendarData()
            calendar.load(events)               # also sets last_success
            with self._lock:
                self._calendar = calendar
                self._error = None
        except Exception as exc:
            # Network drop, expired/revoked auth, missing credentials.json,
            # google packages not installed - keep the last good list.
            report_failure("Calendar update", exc)
            with self._lock:
                self._error = error_text(exc)

    def get_calendar(self):
        """Return the latest CalendarData. It is never changed after this (the next
        poll makes a new one), so treat it as read-only. It has no events and a
        last_success of None until a poll has worked."""
        with self._lock:
            return self._calendar

    def get_error(self):
        """Return the error from the latest poll, or None if it worked."""
        with self._lock:
            return self._error
            
            
            