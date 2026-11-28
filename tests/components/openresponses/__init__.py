"""Tests for the Open Responses integration."""

from collections.abc import AsyncIterator, Sequence
from types import TracebackType
from typing import Self

from openresponses_client import StreamingEvent


class MockStream:
    """Mock of a response stream that yields the given events."""

    def __init__(self, events: Sequence[StreamingEvent | Exception]) -> None:
        """Initialize the stream."""
        self._events = events

    async def __aenter__(self) -> Self:
        """Open the stream."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Close the stream."""

    def __aiter__(self) -> AsyncIterator[StreamingEvent]:
        """Iterate over the events."""
        return self._iterate()

    async def _iterate(self) -> AsyncIterator[StreamingEvent]:
        for event in self._events:
            if isinstance(event, Exception):
                raise event
            yield event
