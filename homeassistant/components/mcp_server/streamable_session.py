"""Enhanced session management for MCP streamable HTTP transport.

Provides session management with proper lifecycle handling,
multiple connection support, and event store integration.
"""

import logging
from typing import Any
import weakref

from .event_store import InMemoryEventStore
from .session import Session

_LOGGER = logging.getLogger(__name__)


class StreamableHTTPSessionManager:
    """Enhanced session manager for streamable HTTP transport.

    Features:
    - Session lifecycle management
    - Multiple concurrent SSE stream tracking
    - Event store per session
    - Proper cleanup on session termination
    """

    def __init__(self) -> None:
        """Initialize the session manager."""
        self._sessions: dict[str, Session] = {}
        self._session_event_stores: dict[str, InMemoryEventStore] = {}
        self._session_streams: dict[str, set[weakref.ReferenceType]] = {}

    def create_session(self, session: Session) -> str:
        """Create a new session and return its ID."""
        # In practice, this would integrate with the existing session manager
        # For now, we'll create a mock implementation
        session_id = f"streamable_{id(session)}"
        self._sessions[session_id] = session
        self._session_event_stores[session_id] = InMemoryEventStore(
            max_events_per_stream=1000
        )
        self._session_streams[session_id] = set()

        _LOGGER.debug("Created streamable HTTP session: %s", session_id)
        return session_id

    def get_session(self, session_id: str) -> Session | None:
        """Get a session by ID."""
        return self._sessions.get(session_id)

    def get_event_store(self, session_id: str) -> InMemoryEventStore | None:
        """Get the event store for a session."""
        return self._session_event_stores.get(session_id)

    def add_stream_connection(self, session_id: str, stream_ref: Any) -> None:
        """Add a stream connection to a session."""
        if session_id in self._session_streams:
            # Use weak reference to avoid keeping connections alive
            self._session_streams[session_id].add(weakref.ref(stream_ref))

    def remove_stream_connection(self, session_id: str, stream_ref: Any) -> None:
        """Remove a stream connection from a session."""
        if session_id in self._session_streams:
            # Remove the weak reference
            to_remove = None
            for ref in self._session_streams[session_id]:
                if ref() is stream_ref:
                    to_remove = ref
                    break
            if to_remove:
                self._session_streams[session_id].discard(to_remove)

    def get_active_streams(self, session_id: str) -> int:
        """Get the number of active streams for a session."""
        if session_id not in self._session_streams:
            return 0

        # Clean up dead references and count live ones
        live_refs = set()
        for ref in self._session_streams[session_id]:
            if ref() is not None:
                live_refs.add(ref)

        self._session_streams[session_id] = live_refs
        return len(live_refs)

    def terminate_session(self, session_id: str) -> bool:
        """Terminate a session and clean up all resources."""
        if session_id not in self._sessions:
            return False

        # Clean up event store
        if session_id in self._session_event_stores:
            event_store = self._session_event_stores[session_id]
            stream_id = f"session_{session_id}"
            event_store.clear_stream(stream_id)
            del self._session_event_stores[session_id]

        # Clean up stream connections
        if session_id in self._session_streams:
            del self._session_streams[session_id]

        # Remove session
        del self._sessions[session_id]

        _LOGGER.debug("Terminated streamable HTTP session: %s", session_id)
        return True

    def cleanup_expired_sessions(self) -> None:
        """Clean up sessions that have no active connections."""
        expired_sessions = [
            session_id
            for session_id in self._sessions
            if self.get_active_streams(session_id) == 0
        ]

        for session_id in expired_sessions:
            _LOGGER.debug("Cleaning up expired session: %s", session_id)
            self.terminate_session(session_id)
