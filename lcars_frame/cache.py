"""
cache.py

A small in-memory cache for data objects, where each item expires after a
number of seconds.

Usage:

    cache = Cache()

    cache.add("weather", weather_data, 600)     # key, data, expiry_secs
    cache.add("calendar", calendar_data)        # expiry_secs defaults to 3600 (1 hour)

    data = cache.get("weather")                 # the data, or None
    if data is None:
        ...                                     # never stored, or it has expired

    cache.remove("weather")
    cache.clear()

Adding an item with a key that is already in the cache replaces it, and
restarts its expiry time. Every time an item is added, all the items that
have expired are purged (deleted) first, so the cache can't fill up with
old data.

The data is stored as it is, not copied, so it must not be changed after it has
been added. Safe to use from several threads.
"""

import threading
import time


class Cache:

    def __init__(self):
        self._items = {}                # key -> (data, expires_at)
        self._lock = threading.Lock()


    # Store data under key, to expire after expiry_secs seconds (default
    # one hour). Purges all expired items first.
    def add(self, key, data, expiry_secs=3600):
        now = time.monotonic()
        expires_at = now + expiry_secs

        with self._lock:
            self._purge(now)
            self._items[key] = (data, expires_at)


    # The data stored under key, or None if there is no such key
    # or it has expired.
    def get(self, key):
        with self._lock:
            item = self._items.get(key)
            if item is None or time.monotonic() >= item[1]:
                return None
            return item[0]


    # Delete the item stored under key, if there is one.
    def remove(self, key):
        with self._lock:
            self._items.pop(key, None)


    # Delete everything.
    def clear(self):
        with self._lock:
            self._items.clear()


    # Delete the expired items. The caller must already hold the lock.
    # An item is stored as (data, expires_at), where expires_at is a
    # time.monotonic() value.
    def _purge(self, now):
        self._items = {key: item for key, item in self._items.items() if item[1] > now}
        
        