"""Utils for bluesound tests."""

import asyncio
from typing import Protocol


class Etag(Protocol):
    """Etag protocol."""

    etag: str


class LongPollingMock[T: Etag]:
    """Mock long polling methods(status, sync_status)."""

    def __init__(self, value: T) -> None:
        """Store value and allows to wait for changes."""
        self._value = value
        self._error: Exception | None = None
        self._event = asyncio.Event()
        self._event.set()

    def trigger(self):
        """Trigger the event without changing the value."""
        self._event.set()

    def set(self, value: T):
        """Set the value and notify all waiting."""
        self._value = value
        self._event.set()

    def set_error(self, error: Exception | None):
        """Set the error and notify all waiting."""
        self._error = error
        self._event.set()

    def get(self) -> T:
        """Get the value without waiting."""
        return self._value

    async def wait(self) -> T:
        """Wait for the value or error to change."""
        await self._event.wait()
        self._event.clear()

        return self._value

    def side_effect(self):
        """Return the side_effect for mocking."""
        last_etag = None

        async def mock(*args, **kwargs) -> T:
            nonlocal last_etag
            if self._error is not None:
                raise self._error

            etag = kwargs.get("etag")
            if etag is None or etag != last_etag:
                last_etag = self.get().etag
                return self.get()

            value = await self.wait()
            last_etag = value.etag

            if self._error is not None:
                raise self._error

            return value

        return mock
