"""Thread-safe set implementation using asyncio for asynchronous operations."""

import asyncio
from collections.abc import Hashable


class AsyncSet:
    """Thread/async-safe set."""

    def __init__(self) -> None:
        """Constructor for AsyncSet. Wraps set with an asyncio.Lock."""
        self._items: set[Hashable] = set()
        self._lock = asyncio.Lock()

    async def add(self, item):
        """Add item to set."""
        async with self._lock:
            self._items.add(item)

    async def discard(self, item):
        """Remove item if present."""
        async with self._lock:
            self._items.discard(item)

    async def remove(self, item):
        """Remove item, raise KeyError if not present."""
        async with self._lock:
            self._items.remove(item)

    async def pop(self):
        """Remove and return arbitrary item."""
        async with self._lock:
            return self._items.pop()

    async def clear(self):
        """Remove all items."""
        async with self._lock:
            self._items.clear()

    async def copy(self):
        """Return a copy of the set."""
        async with self._lock:
            return self._items.copy()

    def __contains__(self, item):
        """Check if item in set."""
        return item in self._items

    def __len__(self):
        """Get size of set."""
        return len(self._items)

    def __bool__(self):
        """Check if set is empty in pythonic way."""
        return bool(self._items)
