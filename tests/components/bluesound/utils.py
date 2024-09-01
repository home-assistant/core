"""Utils for bluesound tests."""

import asyncio
from contextlib import suppress
from typing import Any, Generic, TypeVar

T = TypeVar("T")


class ValueStore(Generic[T]):
    """Store a value and notify all waiting when it changes."""

    def __init__(self, value: T) -> None:
        """Store value and allows to wait for changes."""
        self._value = value
        self._event = asyncio.Event()
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

        async def mock(*args, **kwargs) -> T:
            with suppress(TimeoutError):
                await asyncio.wait_for(self.wait(), 0.1)
            return self.get()

        return mock
