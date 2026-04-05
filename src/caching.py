# src/caching.py

import hashlib
import time
from collections import OrderedDict
from src.config import config


def make_cache_key(prompt: str, max_new_tokens: int) -> str:
    """
    Hash the prompt + params into an anonymous key.
    # NEVER store plaintext identifiers — only the content hash.
    """
    raw = f"{prompt}|max_tokens={max_new_tokens}"
    return hashlib.sha256(raw.encode()).hexdigest()


class InProcessCache:
    """
    LRU cache with TTL expiration and max-entry limits.
    Thread-safe for use with asyncio.
    """

    def __init__(self, max_entries: int = config.CACHE_MAX_ENTRIES,
                 ttl_seconds: float = config.CACHE_TTL_SECONDS):
        self.max_entries = max_entries
        self.ttl_seconds = ttl_seconds
        self._store: OrderedDict = OrderedDict()
        self.hits = 0
        self.misses = 0

    def get(self, key: str):
        """Return cached value if it exists and hasn't expired."""
        if key not in self._store:
            self.misses += 1
            return None

        value, timestamp = self._store[key]

        # Check TTL expiration
        if time.time() - timestamp > self.ttl_seconds:
            del self._store[key]
            self.misses += 1
            return None

        # Move to end (most recently used)
        self._store.move_to_end(key)
        self.hits += 1
        return value

    def set(self, key: str, value: str) -> None:
        """Store a value, evicting oldest entry if at capacity."""
        if key in self._store:
            self._store.move_to_end(key)
        self._store[key] = (value, time.time())

        # Evict oldest entry if over limit (LRU eviction)
        if len(self._store) > self.max_entries:
            self._store.popitem(last=False)

    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    def size(self) -> int:
        return len(self._store)

    def clear(self) -> None:
        self._store.clear()
        self.hits = 0
        self.misses = 0


# Global cache instance
cache = InProcessCache()