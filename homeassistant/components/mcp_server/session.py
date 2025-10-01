"""Model Context Protocol sessions."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass
import logging

from anyio.streams.memory import MemoryObjectSendStream
from mcp.shared.message import SessionMessage

_LOGGER = logging.getLogger(__name__)


@dataclass
class Session:
    """A session for the Model Context Protocol."""

    read_stream_writer: MemoryObjectSendStream[SessionMessage | Exception]


class SessionManager:
    """Manage SSE sessions for the MCP transport layer."""

    def __init__(self) -> None:
        """Initialize the SSE session manager."""
        self._sessions: dict[str, Session] = {}

    @asynccontextmanager
    async def create(self, session: Session) -> AsyncGenerator[str]:
        """Context manager to create a new session ID and close when done."""
        from homeassistant.util import ulid as ulid_util

        session_id = ulid_util.ulid_now()
        _LOGGER.debug("Creating session: %s", session_id)
        self._sessions[session_id] = session
        try:
            yield session_id
        finally:
            _LOGGER.debug("Closing session: %s", session_id)
            self._sessions.pop(session_id, None)

    def get(self, session_id: str) -> Session | None:
        """Get an existing session."""
        return self._sessions.get(session_id)

    def close(self) -> None:
        """Close any open sessions."""
        for session in self._sessions.values():
            session.read_stream_writer.close()
        self._sessions.clear()
