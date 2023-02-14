"""Helper to restore old aiohttp behavior."""
from __future__ import annotations

from aiohttp import web_protocol, web_server


class CancelOnDisconnectRequestHandler(web_protocol.RequestHandler):
    """Request handler that cancels tasks on disconnect."""

    def connection_lost(self, exc: BaseException | None) -> None:
        """Handle connection lost."""
        task_handler = self._task_handler
        super().connection_lost(exc)
        if task_handler is not None:
            task_handler.cancel()


def restore_original_aiohttp_cancel_behavior() -> None:
    """Patch aiohttp to restore cancel behavior.

    Remove this once aiohttp 3.9 is released as we can use
    https://github.com/aio-libs/aiohttp/pull/7128
    """
    web_protocol.RequestHandler = CancelOnDisconnectRequestHandler  # type: ignore[misc]
    web_server.RequestHandler = CancelOnDisconnectRequestHandler  # type: ignore[misc]
