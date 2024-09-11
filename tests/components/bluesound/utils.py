"""Utils for bluesound tests."""

import asyncio
from typing import Protocol


class Etag(Protocol):
    """Etag protocol."""

    etag: str

class ValueStore[T: Etag]:
    """Store a value and notify all waiting when it changes."""

    def __init__(self, value: T) -> None:
        """Store value and allows to wait for changes."""
        self._value = value
        self._event = asyncio.Event()
        self._event.set()

    def trigger(self):
        """Trigger the event without changing the value."""
        self._event.set()

    def set(self, value: T):
        """Set the value and notify all waiting."""
        self._value = value
        self._event.set()

    def get(self) -> T:
        """Get the value without waiting."""
        return self._value

    async def wait(self) -> T:
        """Wait for the value to change."""
        await self._event.wait()
        self._event.clear()

        return self._value

    def long_polling_mock(self):
        """Return a long-polling mock."""
        last_etag = None

        async def mock(*args, **kwargs) -> T:
            nonlocal last_etag
            etag = kwargs.get("etag")
            if etag is None or etag != last_etag:
                last_etag = self.get().etag
                return self.get()

            value = await self.wait()
            last_etag = value.etag

            return value

        return mock
