"""
Background picture downloader for the DeviantArt frame.

Once a day it fetches new pictures from DeviantArt: landscape (wider than tall), big
enough, and never one it has fetched before. DAILY_COUNT of them are Daily Deviations (the
pictures DeviantArt's staff pick each day), and PICTURE_COUNT more are your choices.
Which pictures, and whether mature
ones are allowed, is chosen in deviantart_choices.txt next to this script (it says how):
the galleries of artists you name, topics (DeviantArt's categories, such as digital-art or
photography) and tags. Pictures from all of those are mixed together. If they don't give
enough, or none are named, it uses the Daily Deviations (the pictures DeviantArt's staff
pick each day) of today and the few days before, and then the most popular of the week.

They go in a folder for that day inside the folder it is given, with a credits.json
giving the title and artist of each, which the frame shows in the corner. Then the
oldest pictures are deleted, so that only the newest KEEP_COUNT are kept.

It needs a DeviantArt API key: log in to DeviantArt, register an application at
https://www.deviantart.com/developers/register, and put its client_id and client_secret
in a file called deviantart_key.txt next to this script, on two lines:

    12345
    0123456789abcdef0123456789abcdef

The key and the choices are read each time, so they can be changed without restarting.
To check the key works and list the topics there are to choose from, run (in ~/lcars3):

    python3 -m deviantart_frame.deviantart_library topics

If a download fails (no internet, no key...), the pictures already there are kept, and
it tries again every RETRY_INTERVAL.
Uses only the Python standard library.
"""

import json
import os
import shutil
import sys
import threading
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta

import screens as scr     # for the screen size


# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

TOKEN_URL = "https://www.deviantart.com/oauth2/token"
API_URL = "https://www.deviantart.com/api/v1/oauth2"
HERE = os.path.dirname(os.path.abspath(__file__))
KEY_FILE = os.path.join(HERE, "deviantart_key.txt")
CHOICES_FILE = os.path.join(HERE, "deviantart_choices.txt")
SEEN_FILE = "seen.json"         # the pictures fetched before, kept in the folder given

PICTURE_COUNT = 30              # how many new pictures to fetch each day from the choices...
DAILY_COUNT = 10                # ...and how many of the Daily Deviations as well...
KEEP_COUNT = 400                # ...and how many to keep: the oldest beyond this are deleted
MAX_ZOOM = 1.6                  # pictures that would have to be zoomed more than this to fill the screen
                                # are low resolution, and passed over (1.2: at least 1600 x 900)
MAX_ORIGINAL_BYTES = 25_000_000 # a downloadable original bigger than this is too slow to show
DAILY_DAYS = 7                  # Daily Deviations: today's and this many days before (enough
                                # to find DAILY_COUNT that are wide and big enough)...
POPULAR_TIMERANGE = "1week"     # ...then the most popular of this long ("1week", "1month", "alltime")
PAGE_SIZE = 24                  # pictures are asked for this many at a time (24 is the most allowed)...
MAX_PAGES = 5                   # ...for at most this many pages from each artist, topic, tag or popular
SEEN_LIMIT = 5000               # how many fetched pictures to remember

CHECK_INTERVAL = 10 * 60        # seconds between checks for a new day
RETRY_INTERVAL = 30 * 60        # seconds before trying again after a failure
REQUEST_TIMEOUT = 30            # seconds
REQUEST_PAUSE = 1               # seconds between requests, to be polite
MAX_TOPIC_PAGES = 30            # most pages of topics "topics" will ask for (10 a page)

PICTURE_TYPES = (".jpg", ".jpeg", ".png", ".gif", ".webp")
USER_AGENT = "lcars-deviantart-frame/1.0 (home display; python-urllib)"

# Written to CHOICES_FILE if it isn't there
DEFAULT_CHOICES = """\
# What the DeviantArt frame shows. Lines starting with # are ignored.
# Changes are used the next time it downloads (once a day).
#
# Name as many artists, topics and tags as you like, one per line; pictures from all of
# them are mixed together. With none, it shows the Daily Deviations and the most popular.
#
#   artist: someusername      the artist's gallery, newest first (the name in their
#                             page's address: deviantart.com/someusername)
#   topic: digital-art        one of DeviantArt's categories: to list them all, run
#                             python3 -m deviantart_frame.deviantart_library topics
#   tag: landscape            pictures tagged with this, newest first
#
# mature: yes                 also show pictures marked as mature (NSFW); no: don't
# fill: yes                   if those give fewer than 30 new pictures in a day, make up
#                             the rest from the Daily Deviations and the most popular

mature: yes
fill: yes

# artist: someusername
# topic: digital-art
# topic: fantasy
# tag: landscape
"""


_thread = None


class LibraryError(Exception):
    """Raised for any failure talking to DeviantArt."""


# --------------------------------------------------------------------------
# The key and the choices
# --------------------------------------------------------------------------

# The client_id and client_secret from KEY_FILE, or None if it isn't there or isn't complete
def read_key():
    try:
        with open(KEY_FILE, encoding="utf-8") as file:
            lines = [line.strip() for line in file if line.strip() and not line.strip().startswith("#")]
    except OSError:
        return None

    return (lines[0], lines[1]) if len(lines) >= 2 else None


# The choices in CHOICES_FILE (which is made if it isn't there), as a dict:
# {"artist": [...], "topic": [...], "tag": [...], "mature": bool, "fill": bool}
def read_choices():
    if not os.path.exists(CHOICES_FILE):
        try:
            with open(CHOICES_FILE, "w", encoding="utf-8") as file:
                file.write(DEFAULT_CHOICES)
        except OSError:
            pass

    choices = {"artist": [], "topic": [], "tag": [], "mature": True, "fill": True}

    try:
        with open(CHOICES_FILE, encoding="utf-8") as file:
            lines = file.read().splitlines()
    except OSError:
        lines = []

    for line in lines:
        line = line.split("#", 1)[0].strip()
        if ":" not in line:
            continue

        name, value = (part.strip() for part in line.split(":", 1))
        name = name.lower()

        if name in ("artist", "topic", "tag") and value:
            choices[name].append(value)
        elif name in ("mature", "fill"):
            choices[name] = value.lower() in ("yes", "y", "true", "on", "1")
        else:
            print(f"Not understood in {CHOICES_FILE}: {line}")

    return choices


# --------------------------------------------------------------------------
# The DeviantArt API
# --------------------------------------------------------------------------

# Send a request and decode the JSON answer
def request_json(url, data=None, token=None):
    headers = {"User-Agent": USER_AGENT}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    body = urllib.parse.urlencode(data).encode() if data is not None else None
    request = urllib.request.Request(url, data=body, headers=headers)

    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        try:
            detail = json.load(exc).get("error_description") or ""
        except Exception:
            detail = ""
        if exc.code == 429:
            raise LibraryError("DeviantArt says too many requests: try later") from None
        raise LibraryError(f"HTTP {exc.code}: {detail or exc.reason}") from None
    except urllib.error.URLError as exc:
        raise LibraryError(f"Network error: {exc.reason}") from None
    except (TimeoutError, OSError) as exc:
        raise LibraryError(f"Connection error: {exc}") from None
    except ValueError as exc:
        raise LibraryError(f"Invalid JSON: {exc}") from None


# An access token for the API, which lasts an hour
def get_token(key):
    client_id, client_secret = key
    try:
        answer = request_json(TOKEN_URL, data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        })
    except LibraryError as exc:
        raise LibraryError(f"DeviantArt didn't accept the key in {KEY_FILE} ({exc})") from None

    token = answer.get("access_token")
    if not token:
        raise LibraryError("DeviantArt gave no access token")
    return token


# Ask the API for something
def api(path, token, mature, **params):
    params["mature_content"] = "true" if mature else "false"
    return request_json(f"{API_URL}{path}?{urllib.parse.urlencode(params)}", token=token)


# --------------------------------------------------------------------------
# Choosing the pictures
# --------------------------------------------------------------------------

# The file type of a picture's address (.jpg, .png...), from the end of its path
def picture_type(url):
    return os.path.splitext(urllib.parse.urlparse(url).path)[1].lower()


# True if a deviation is one to show: a picture, landscape, and not mature unless that is
# allowed (whether it is big enough is seen to by best_picture)
def is_wanted(deviation, mature):
    content = deviation.get("content") or {}
    width, height = content.get("width") or 0, content.get("height") or 0

    return bool(content.get("src")
                and (mature or not deviation.get("is_mature"))
                and not deviation.get("is_deleted")
                and width > height
                and picture_type(content["src"]) in PICTURE_TYPES)


# True if a picture of width x height is big enough to fill the screen without being
# zoomed more than MAX_ZOOM
def is_big_enough(width, height):
    return width > 0 and height > 0 and max(scr.SCREEN_WIDTH / width, scr.SCREEN_HEIGHT / height) <= MAX_ZOOM


# The address of a version of the deviation big enough to fill the screen, or None if it
# hasn't got one. The one shown on its page is used if it is big enough; if not, and the
# artist lets it be downloaded, the original (unless it is more than MAX_ORIGINAL_BYTES).
def best_picture(deviation, token, mature):
    content = deviation["content"]
    if is_big_enough(content.get("width") or 0, content.get("height") or 0):
        return content["src"]

    if not deviation.get("is_downloadable"):
        return None

    try:
        original = api(f"/deviation/download/{deviation['deviationid']}", token, mature)
    except LibraryError as exc:
        print(f"Can't get the original of {deviation.get('url')}: {exc}")
        return None
    finally:
        time.sleep(REQUEST_PAUSE)

    if (original.get("src")
            and is_big_enough(original.get("width") or 0, original.get("height") or 0)
            and (original.get("filesize") or 0) <= MAX_ORIGINAL_BYTES
            and picture_type(original["src"]) in PICTURE_TYPES):
        return original["src"]

    return None


# Keeps count of the requests that worked, so that it can tell when every one failed
class Requests:
    def __init__(self):
        self.worked = 0
        self.failed = 0


# The deviations from one place in the API, a page at a time, up to MAX_PAGES pages.
# If a request fails, it says so and stops.
def paged(what, path, token, mature, requests, **params):
    offset = 0

    for _ in range(MAX_PAGES):
        try:
            page = api(path, token, mature, offset=offset, limit=PAGE_SIZE, **params)
            requests.worked += 1
        except LibraryError as exc:
            print(f"Can't get the pictures of {what}: {exc}")
            requests.failed += 1
            return

        yield from page.get("results") or []

        if not page.get("has_more") or page.get("next_offset") is None:
            return
        offset = page["next_offset"]
        time.sleep(REQUEST_PAUSE)


# The Daily Deviations of today and the DAILY_DAYS before it
def daily_deviations(token, mature, requests):
    for days_ago in range(DAILY_DAYS + 1):
        day = (date.today() - timedelta(days=days_ago)).isoformat()
        try:
            yield from api("/browse/dailydeviations", token, mature, date=day).get("results") or []
            requests.worked += 1
        except LibraryError as exc:
            print(f"Can't get the Daily Deviations of {day}: {exc}")
            requests.failed += 1
        time.sleep(REQUEST_PAUSE)


# One from each of the lists in turn, until they have all run out
def interleave(sources):
    sources = list(sources)
    while sources:
        for source in list(sources):
            try:
                yield next(source)
            except StopIteration:
                sources.remove(source)


# The deviations to look through, best first: those of the chosen artists, topics and tags,
# mixed together, and then (if none are chosen, or "fill" is on) the Daily Deviations and the
# most popular
def candidates(token, choices, requests):
    mature = choices["mature"]

    chosen = ([paged(f"artist {name}", "/gallery/all", token, mature, requests, username=name)
               for name in choices["artist"]] +
              [paged(f"topic {name}", "/browse/topic", token, mature, requests, topic=name)
               for name in choices["topic"]] +
              [paged(f"tag {name}", "/browse/tags", token, mature, requests, tag=name)
               for name in choices["tag"]])

    yield from interleave(chosen)

    if not chosen or choices["fill"]:
        yield from daily_deviations(token, mature, requests)
        yield from paged("popular", "/browse/popular", token, mature, requests, timerange=POPULAR_TIMERANGE)


# What the frame shows as a picture's credit
def credit_text(deviation):
    title = (deviation.get("title") or "untitled").strip()
    artist = (deviation.get("author") or {}).get("username") or "unknown"
    return f"{title} by {artist} on DeviantArt"


# --------------------------------------------------------------------------
# The pictures kept
# --------------------------------------------------------------------------

def read_seen(folder):
    try:
        with open(os.path.join(folder, SEEN_FILE), encoding="utf-8") as file:
            return json.load(file)
    except (OSError, ValueError):
        return []


def write_seen(folder, seen):
    with open(os.path.join(folder, SEEN_FILE), "w", encoding="utf-8") as file:
        json.dump(seen[-SEEN_LIMIT:], file)


def is_picture(name):
    return os.path.splitext(name)[1].lower() in PICTURE_TYPES


# Delete the oldest pictures, so that only the newest KEEP_COUNT are left, and then any
# day's folder with no pictures left in it. The days' folders are named by their date, so
# the newest are last in name order.
def prune(folder):
    days = sorted((name for name in os.listdir(folder)
                   if not name.startswith(".") and os.path.isdir(os.path.join(folder, name))), reverse=True)
    kept = 0

    for day in days:
        path = os.path.join(folder, day)

        for name in sorted(filter(is_picture, os.listdir(path))):
            if kept < KEEP_COUNT:
                kept += 1
            else:
                os.remove(os.path.join(path, name))

        if not any(map(is_picture, os.listdir(path))):
            shutil.rmtree(path, ignore_errors=True)


# Fetch one picture to a file
def download(url, path):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response, open(path, "wb") as file:
        shutil.copyfileobj(response, file)


# Fetch today's new pictures into folder/<today>. They are fetched into a hidden folder (the
# frame skips folders starting with "."), which is renamed when it is done, so that the frame
# never sees half a set. Then the oldest pictures are deleted.
# Download up to count pictures from source (deviations, best first) into the working
# folder, passing over any that aren't wanted or were fetched before. Each is added to
# credits (by its file name) and seen; seenIds is the ids in seen, for looking them up.
def fetch(source, count, token, mature, working, credits, seen, seenIds):
    fetched = 0

    for deviation in source:
        if fetched >= count:
            return

        devId = deviation.get("deviationid")
        if not devId or devId in seenIds or not is_wanted(deviation, mature):
            continue

        seenIds.add(devId)
        src = best_picture(deviation, token, mature)

        if src is None:     # low resolution: remembered, so that it isn't looked at again
            seen.append(devId)
            continue

        name = f"{len(credits):02d}{picture_type(src)}"

        try:
            download(src, os.path.join(working, name))
        except Exception as exc:
            print(f"Picture download failed: {deviation.get('url')}: {exc}")
            continue

        credits[name] = credit_text(deviation)
        seen.append(devId)
        fetched += 1
        print(f"Downloaded picture {name}: {credits[name]}", flush=True)
        time.sleep(REQUEST_PAUSE)


# Returns True if it worked, False if not. Never raises.
def update_pictures(folder):
    today = date.today().isoformat()
    final = os.path.join(folder, today)
    working = os.path.join(folder, "." + today)

    key = read_key()
    if key is None:
        print(f"No DeviantArt key, so no new pictures: put your client_id and client_secret in {KEY_FILE}")
        return False

    try:
        token = get_token(key)
        choices = read_choices()
        requests = Requests()
        seen = read_seen(folder)
        seenIds = set(seen)

        shutil.rmtree(working, ignore_errors=True)
        os.makedirs(working)
        credits = {}
        mature = choices["mature"]

        # DAILY_COUNT of the Daily Deviations, then PICTURE_COUNT more from the choices
        # (none the same as each other, or as any fetched before)
        fetch(daily_deviations(token, mature, requests), DAILY_COUNT,
              token, mature, working, credits, seen, seenIds)
        fetch(candidates(token, choices, requests), PICTURE_COUNT,
              token, mature, working, credits, seen, seenIds)

        if not credits:
            if requests.worked == 0:
                print("Can't get any pictures from DeviantArt: keeping the old ones")
            else:
                print("No new pictures found: keeping the old ones (try more artists, topics or tags)")
            shutil.rmtree(working, ignore_errors=True)
            return False

        with open(os.path.join(working, "credits.json"), "w", encoding="utf-8") as file:
            json.dump(credits, file, indent=1, ensure_ascii=False)

        shutil.rmtree(final, ignore_errors=True)
        os.rename(working, final)
        write_seen(folder, seen)
        prune(folder)

        print(f"Downloaded {len(credits)} pictures for {today}")
        return True

    except LibraryError as exc:
        print(f"No new pictures: {exc}")
        shutil.rmtree(working, ignore_errors=True)
        return False

    except Exception:   # safety net: never let the thread die
        print("Unexpected error downloading pictures")
        traceback.print_exc()
        shutil.rmtree(working, ignore_errors=True)
        return False


# --------------------------------------------------------------------------
# Background thread
# --------------------------------------------------------------------------

def _worker(folder):
    print("DeviantArt downloader started")

    while True:
        if os.path.isdir(os.path.join(folder, date.today().isoformat())):
            time.sleep(CHECK_INTERVAL)
        elif update_pictures(folder):
            time.sleep(CHECK_INTERVAL)
        else:
            time.sleep(RETRY_INTERVAL)


def start_download_thread(folder):
    """Start the background downloader (safe to call more than once)."""
    global _thread
    read_choices()      # makes the choices file now if it isn't there, so it can be found
    if _thread is not None and _thread.is_alive():
        return _thread
    os.makedirs(folder, exist_ok=True)
    _thread = threading.Thread(target=_worker, args=(folder,), name="deviantart-downloader", daemon=True)
    _thread.start()
    return _thread


# --------------------------------------------------------------------------
# Run by hand: python3 -m deviantart_frame.deviantart_library topics
# --------------------------------------------------------------------------

# Check the key works, and list the topics that can be chosen in the choices file
def list_topics():
    key = read_key()
    if key is None:
        sys.exit(f"No key: put your client_id and client_secret in {KEY_FILE}")

    try:
        token = get_token(key)
        print("The key works. The topics there are to choose from:\n")
        seen = set()
        cursors = set()
        cursor = None

        # Each page is printed as it comes, so it can be seen to be working. The paging
        # stops when DeviantArt says there is no more, or gives a cursor it has given
        # before, or a page with nothing new on it, or after MAX_TOPIC_PAGES pages,
        # so it can't go round for ever.
        for _ in range(MAX_TOPIC_PAGES):
            params = {"limit": 10, **({"cursor": cursor} if cursor else {})}
            page = api("/browse/topics", token, True, **params)

            new = 0
            for topic in page.get("results") or []:
                canonical = topic.get("canonical_name")
                if canonical and canonical not in seen:
                    seen.add(canonical)
                    new += 1
                    print(f"  topic: {canonical:30} ({topic.get('name')})", flush=True)

            cursor = page.get("next_cursor")
            if not page.get("has_more") or not cursor or cursor in cursors or new == 0:
                break
            cursors.add(cursor)
            time.sleep(REQUEST_PAUSE)

    except LibraryError as exc:
        sys.exit(str(exc))

    print(f"\n{len(seen)} topics")


if __name__ == "__main__":
    if sys.argv[1:] == ["topics"]:
        list_topics()
    else:
        print("Usage: python3 -m deviantart_frame.deviantart_library topics")
