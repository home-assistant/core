"""Runtime helpers for the MCP Server integration."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from mcp.server.auth.provider import TokenVerifier  # type: ignore[import-untyped]
from mcp.server.auth.settings import AuthSettings  # type: ignore[import-untyped]
from mcp.server.fastmcp import FastMCP  # type: ignore[import-untyped]
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager  # type: ignore[import-untyped]

from .event_store import InMemoryEventStore
from .session import SessionManager

_LOGGER = logging.getLogger(__name__)


class StreamableHTTPManagerRunner:
    """Managed lifecycle wrapper around ``StreamableHTTPSessionManager``."""

    def __init__(self, manager: StreamableHTTPSessionManager) -> None:
        self._manager = manager
        self._stop_event: asyncio.Event | None = None
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Start the session manager background task if not already running."""
        if self._task is not None:
            return

        self._stop_event = asyncio.Event()
        self._task = asyncio.create_task(self._run(), name="mcp_streamable_http")

    async def stop(self) -> None:
        """Signal the background task to stop and wait for completion."""
        if self._task is None:
            return

        assert self._stop_event is not None
        self._stop_event.set()
        task = self._task
        self._task = None
        try:
            await task
        except asyncio.CancelledError:
            raise
        except Exception:  # pragma: no cover - defensive
            _LOGGER.exception("Streamable HTTP session manager stopped with error")
        finally:
            self._stop_event = None

    async def _run(self) -> None:
        assert self._stop_event is not None
        try:
            async with self._manager.run():
                await self._stop_event.wait()
        except asyncio.CancelledError:
            raise
        except Exception:  # pragma: no cover - defensive
            _LOGGER.exception("Streamable HTTP session manager crashed unexpectedly")
        finally:
            self._task = None


@dataclass(slots=True)
class MCPServerRuntime:
    """Container for runtime resources tied to a config entry."""

    session_manager: SessionManager
    fast_server: FastMCP[Any]
    streamable_manager: StreamableHTTPSessionManager
    streamable_runner: StreamableHTTPManagerRunner
    event_store: InMemoryEventStore
    auth_settings: AuthSettings
    token_verifier: TokenVerifier
