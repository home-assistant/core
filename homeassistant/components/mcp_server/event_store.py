"""Event store for MCP streamable HTTP transport resumability support."""

from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass
import logging

from mcp import types

_LOGGER = logging.getLogger(__name__)

# Type aliases for clarity
StreamId = str
EventId = str


@dataclass
class EventMessage:
    """A JSONRPCMessage with an event ID for stream resumability."""

    message: types.JSONRPCMessage
    event_id: str


class EventStore(ABC):
    """Interface for resumability support via event storage."""

    @abstractmethod
    async def store_event(
        self, stream_id: StreamId, message: types.JSONRPCMessage
    ) -> EventId:
        """Store an event and return its ID.

        Args:
            stream_id: ID of the stream the event belongs to.
            message: The JSON-RPC message to store.

        Returns:
            The generated event ID for the stored event.

        """

    @abstractmethod
    async def replay_events_after(
        self, last_event_id: EventId, stream_id: StreamId
    ) -> list[EventMessage]:
        """Replay events that occurred after the specified event ID.

        Args:
            last_event_id: The ID of the last event the client received.
            stream_id: The stream ID to replay events for.

        Returns:
            List of events that occurred after the specified event ID.

        """


class InMemoryEventStore(EventStore):
    """Simple in-memory event store for testing and development.

    Note: This is for demonstration purposes only. For production use,
    consider implementing a persistent storage solution.
    """

    def __init__(self, max_events_per_stream: int = 100) -> None:
        """Initialize the event store.

        Args:
            max_events_per_stream: Maximum number of events to keep per stream.

        """
        self.max_events_per_stream = max_events_per_stream
        # Stream ID -> deque of events
        self._streams: dict[StreamId, deque[EventMessage]] = {}
        # Event ID -> EventMessage for quick lookup
        self._event_index: dict[EventId, EventMessage] = {}
        self._next_event_id = 1

    async def store_event(
        self, stream_id: StreamId, message: types.JSONRPCMessage
    ) -> EventId:
        """Store an event and return its ID."""
        event_id = str(self._next_event_id)
        self._next_event_id += 1

        event_message = EventMessage(message=message, event_id=event_id)

        # Initialize stream if it doesn't exist
        if stream_id not in self._streams:
            self._streams[stream_id] = deque(maxlen=self.max_events_per_stream)

        # Add to stream and index
        self._streams[stream_id].append(event_message)
        self._event_index[event_id] = event_message

        _LOGGER.debug("Stored event %s for stream %s", event_id, stream_id)
        return event_id

    async def replay_events_after(
        self, last_event_id: EventId, stream_id: StreamId
    ) -> list[EventMessage]:
        """Replay events that occurred after the specified event ID."""
        if stream_id not in self._streams:
            return []

        replay_events = []
        stream_events = self._streams[stream_id]

        # Find the position of the last_event_id
        start_replay = False
        if not last_event_id:
            # If no last event ID, replay all events
            start_replay = True

        for event_message in stream_events:
            if start_replay:
                replay_events.append(event_message)
            elif event_message.event_id == last_event_id:
                # Start replaying from the next event
                start_replay = True

        _LOGGER.debug(
            "Replaying %d events for stream %s after %s",
            len(replay_events),
            stream_id,
            last_event_id,
        )
        return replay_events

    def get_event_count(self, stream_id: StreamId) -> int:
        """Get the number of stored events for a stream."""
        return len(self._streams.get(stream_id, []))

    def clear_stream(self, stream_id: StreamId) -> None:
        """Clear all events for a specific stream."""
        if stream_id in self._streams:
            # Remove events from index
            for event in self._streams[stream_id]:
                if event.event_id in self._event_index:
                    del self._event_index[event.event_id]
            # Clear the stream
            del self._streams[stream_id]
            _LOGGER.debug("Cleared all events for stream %s", stream_id)
