"""A small sample repository for local retrieval."""
import time


class ExpiringCache:
    """Store values briefly and discard them after their time to live."""
    def __init__(self, ttl_seconds=60):
        self.ttl_seconds = ttl_seconds
        self.entries = {}

    def put(self, key, value):
        self.entries[key] = (time.monotonic() + self.ttl_seconds, value)

    def get(self, key):
        expires, value = self.entries[key]
        if time.monotonic() >= expires:
            del self.entries[key]
            raise KeyError(key)
        return value
