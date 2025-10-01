"""In-memory event store enabling resumable StreamableHTTP sessions."""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass
from uuid import uuid4

from mcp.server.streamable_http import (  # type: ignore[import-untyped]
    EventCallback,
    EventId,
    EventMessage,
    EventStore,
    StreamId,
)
from mcp.types import JSONRPCMessage  # type: ignore[import-untyped]

_LOGGER = logging.getLogger(__name__)


@dataclass
class EventEntry:
    """Represents an event entry in the in-memory store."""

    event_id: EventId
    stream_id: StreamId
    message: JSONRPCMessage


class InMemoryEventStore(EventStore):
    """Simple in-memory implementation of the StreamableHTTP event store."""

    def __init__(self, max_events_per_stream: int = 100) -> None:
        self.max_events_per_stream = max_events_per_stream
        self.streams: dict[StreamId, deque[EventEntry]] = {}
        self.event_index: dict[EventId, EventEntry] = {}

    async def store_event(self, stream_id: StreamId, message: JSONRPCMessage) -> EventId:
        event_id = str(uuid4())
        entry = EventEntry(event_id=event_id, stream_id=stream_id, message=message)

        if stream_id not in self.streams:
            self.streams[stream_id] = deque(maxlen=self.max_events_per_stream)

        if len(self.streams[stream_id]) == self.max_events_per_stream:
            oldest = self.streams[stream_id][0]
            self.event_index.pop(oldest.event_id, None)

        self.streams[stream_id].append(entry)
        self.event_index[event_id] = entry
        return event_id

    async def replay_events_after(
        self,
        last_event_id: EventId,
        send_callback: EventCallback,
    ) -> StreamId | None:
        entry = self.event_index.get(last_event_id)
        if entry is None:
            _LOGGER.debug("Event ID %s not found during replay", last_event_id)
            return None

        stream_id = entry.stream_id
        events = self.streams.get(stream_id, deque())

        found_anchor = False
        for event in events:
            if found_anchor:
                await send_callback(EventMessage(event.message, event.event_id))
            elif event.event_id == last_event_id:
                found_anchor = True

        return stream_id
