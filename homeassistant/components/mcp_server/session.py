"""Model Context Protocol sessions.

A session is a long-lived connection between the client and server that is used
to exchange messages. The server pushes messages to the client over the session
and the client sends messages to the server over the session.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass
import logging

from anyio.streams.memory import MemoryObjectSendStream
from mcp import types

from homeassistant.util import ulid

_LOGGER = logging.getLogger(__name__)


@dataclass
class Session:
    """A session for the Model Context Protocol."""

    read_stream_writer: MemoryObjectSendStream[types.JSONRPCMessage | Exception]


class SessionManager:
    """Manage SSE sessions for the MCP transport layer.

    This class is used to manage the lifecycle of SSE sessions. It is responsible for
    creating new sessions, resuming existing sessions, and closing sessions.
    """

    def __init__(self) -> None:
        """Initialize the SSE server transport."""
        self._sessions: dict[str, Session] = {}

    @asynccontextmanager
    async def create(self, session: Session) -> AsyncGenerator[str]:
        """Context manager to create a new session ID and close when done."""
        session_id = ulid.ulid_now()
        _LOGGER.debug("Creating session: %s", session_id)
        self._sessions[session_id] = session
        try:
            yield session_id
        finally:
            _LOGGER.debug("Closing session: %s", session_id)
            if session_id in self._sessions:  # close() may have already been called
                self._sessions.pop(session_id)

    def get(self, session_id: str) -> Session | None:
        """Get an existing session."""
        return self._sessions.get(session_id)

    def close(self) -> None:
        """Close any open sessions."""
        for session in self._sessions.values():
            session.read_stream_writer.close()
        self._sessions.clear()
