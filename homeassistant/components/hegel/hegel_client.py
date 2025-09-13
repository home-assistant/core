from __future__ import annotations

import asyncio
import logging
from collections import deque
from typing import Optional, Callable

_LOGGER = logging.getLogger(__name__)

CR = "\r"


class HegelClient:
    """Async client for Hegel amplifiers with push + command support."""

    def __init__(self, host: str, port: int = 50001):
        self._host = host
        self._port = port
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._lock = asyncio.Lock()

        # Lifecycle
        self._stopping = False
        self._listen_task: asyncio.Task | None = None
        self._manager_task: asyncio.Task | None = None
        self._connected_event = asyncio.Event()

        # Pending commands
        self._pending: deque[asyncio.Future[str]] = deque()

        # Push callback
        self._on_push: Optional[Callable[[str], None]] = None

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    async def start(self) -> None:
        """Start connection manager (runs forever until stop())."""
        if self._manager_task:
            return
        self._stopping = False
        self._manager_task = asyncio.create_task(self._manage_connection())

    async def stop(self) -> None:
        """Stop everything and close the connection."""
        self._stopping = True
        if self._manager_task:
            self._manager_task.cancel()
            self._manager_task = None
        await self._close_connection()

    def add_push_callback(self, callback: Callable[[str], None]) -> None:
        """Register callback for push messages."""
        self._on_push = callback

    async def send(
        self, command: str, expect_reply: bool = True, timeout: float = 5.0
    ) -> Optional[str]:
        """Send command and optionally wait for reply."""
        async with self._lock:
            await self.ensure_connected()
            assert self._writer is not None

            _LOGGER.debug("TX: %s", command.strip())
            fut: asyncio.Future[str] | None = None
            if expect_reply:
                fut = asyncio.get_event_loop().create_future()
                self._pending.append(fut)

            try:
                self._writer.write(command.encode())
                await self._writer.drain()
            except Exception as err:
                _LOGGER.error("Send failed: %s", err)
                if fut and not fut.done():
                    fut.set_exception(err)
                await self._close_connection()
                raise

        if not fut:
            return None

        try:
            return await asyncio.wait_for(fut, timeout=timeout)
        except asyncio.TimeoutError:
            _LOGGER.warning("Timeout waiting for reply to %s", command.strip())
            if not fut.done():
                fut.set_exception(asyncio.TimeoutError())
            raise

    async def ensure_connected(self, timeout: float = 5.0) -> None:
        """Wait until connected (or fail after timeout)."""
        try:
            await asyncio.wait_for(self._connected_event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            raise TimeoutError("Timeout waiting for connection")
    # ------------------------------------------------------------------ #
    # Connection Management
    # ------------------------------------------------------------------ #

    async def _manage_connection(self) -> None:
        """Keep the connection alive with reconnect/backoff."""
        backoff = 1.0
        max_backoff = 60.0

        while not self._stopping:
            try:
                await self._open_connection()
                backoff = 1.0  # reset backoff
                if self._listen_task:
                    await self._listen_task  # wait until disconnect
            except asyncio.CancelledError:
                break
            except Exception as err:
                _LOGGER.warning(
                    "Connection attempt failed: %s — retrying in %.1fs", err, backoff
                )
                await asyncio.sleep(backoff)
                backoff = min(max_backoff, backoff * 2)

        _LOGGER.debug("Connection manager exiting")

    async def _open_connection(self) -> None:
        """Open TCP connection and start listener."""
        if self._reader or self._writer:
            return
        _LOGGER.debug("Opening connection to %s:%s", self._host, self._port)
        self._reader, self._writer = await asyncio.open_connection(
            self._host, self._port
        )
        self._connected_event.set()
        _LOGGER.info("Connected to Hegel at %s:%s", self._host, self._port)
        self._listen_task = asyncio.create_task(self._listen_loop())

    async def _close_connection(self) -> None:
        """Close TCP connection and cleanup."""
        self._connected_event.clear()
        if self._writer:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass
        self._reader = None
        self._writer = None

        if self._listen_task:
            self._listen_task.cancel()
            self._listen_task = None

        # Fail all pending futures
        while self._pending:
            fut = self._pending.popleft()
            if not fut.done():
                fut.set_exception(ConnectionError("Connection closed"))

    # ------------------------------------------------------------------ #
    # Listening / Routing
    # ------------------------------------------------------------------ #

    async def _listen_loop(self) -> None:
        """Background reader loop to handle both replies and push updates."""
        assert self._reader is not None
        try:
            while not self._reader.at_eof():
                line = await self._reader.readuntil(separator=b"\r")
                msg = line.decode(errors="ignore").strip()
                handled = False

                # Route to pending future if waiting
                if self._pending:
                    fut = self._pending.popleft()
                    if not fut.done():
                        fut.set_result(msg)
                        _LOGGER.debug("RX (reply): %s", msg)
                        handled = True

                # Otherwise push
                if not handled:
                    _LOGGER.debug("RX (push): %s", msg)
                    if self._on_push:
                        try:
                            self._on_push(msg)
                        except Exception as err:
                            _LOGGER.error("Push callback failed: %s", err)

        except asyncio.CancelledError:
            pass
        except Exception as err:
            _LOGGER.error("Listen loop failed: %s", err)
        finally:
            await self._close_connection()
