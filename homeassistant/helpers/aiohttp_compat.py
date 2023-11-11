"""Helper to restore old aiohttp behavior."""
from __future__ import annotations

from aiohttp import web, web_protocol, web_server


class CancelOnDisconnectRequestHandler(web_protocol.RequestHandler):
    """Request handler that cancels tasks on disconnect."""

    def connection_lost(self, exc: BaseException | None) -> None:
        """Handle connection lost."""
        task_handler = self._task_handler
        super().connection_lost(exc)
        if task_handler is not None:
            task_handler.cancel("aiohttp connection lost")


def restore_original_aiohttp_cancel_behavior() -> None:
    """Patch aiohttp to restore cancel behavior.

    Remove this once aiohttp 3.9 is released as we can use
    https://github.com/aio-libs/aiohttp/pull/7128
    """
    web_protocol.RequestHandler = CancelOnDisconnectRequestHandler  # type: ignore[misc]
    web_server.RequestHandler = CancelOnDisconnectRequestHandler  # type: ignore[misc]


def enable_compression(response: web.Response) -> None:
    """Enable compression on the response."""
    #
    # Set _zlib_executor_size in the constructor once support for
    # aiohttp < 3.9.0 is dropped
    #
    # We want large zlib payloads to be compressed in the executor
    # to avoid blocking the event loop.
    #
    # 32KiB was chosen based on testing in production.
    # aiohttp will generate a warning for payloads larger than 1MiB
    #
    response._zlib_executor_size = 32768  # pylint: disable=protected-access
    response.enable_compression()
