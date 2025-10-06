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
        # small lock to protect writer/connection operations only
        self._write_lock = asyncio.Lock()

        # Lifecycle
        self._stopping = False
        self._listen_task: asyncio.Task | None = None
        self._manager_task: asyncio.Task | None = None
        self._connected_event = asyncio.Event()
        # prevent concurrent connect attempts
        self._reconnect_lock = asyncio.Lock()

        # Pending commands: FIFO futures consumers will fulfill
        self._pending: deque[asyncio.Future[str]] = deque()

        # Push callback
        self._on_push: Optional[Callable[[str], None]] = None

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    async def start(self) -> None:
        """Start connection manager (runs forever until stop())."""
        # Prevent multiple concurrent manager tasks
        if self._manager_task and not self._manager_task.done():
            _LOGGER.debug("Connection manager already running — skipping start()")
            return

        self._stopping = False
        self._manager_task = asyncio.create_task(self._manage_connection())
        _LOGGER.debug("Connection manager started")

    async def stop(self) -> None:
        """Stop everything and close the connection."""
        self._stopping = True
        if self._manager_task:
            self._manager_task.cancel()
            try:
                await self._manager_task
            except asyncio.CancelledError:
                pass
            self._manager_task = None
        await self._close_connection()

    def add_push_callback(self, callback: Callable[[str], None]) -> None:
        """Register callback for push messages."""
        self._on_push = callback

    async def send(
        self, command: str, expect_reply: bool = True, timeout: float = 5.0
    ) -> Optional[str]:
        """Send command and optionally wait for reply.

        Important: we only hold the _write_lock for writer access and pending append.
        Waiting for reply is done outside the lock to avoid deadlocks with the reader.
        """
        # normalize line ending: Hegel uses CR
        if not command.endswith(CR):
            command_to_send = command + CR
        else:
            command_to_send = command

        # ensure connected and write under lock
        await self.ensure_connected()
        fut: asyncio.Future[str] | None = None
        async with self._write_lock:
            if expect_reply:
                fut = asyncio.get_event_loop().create_future()
                self._pending.append(fut)

            try:
                assert self._writer is not None
                _LOGGER.debug("TX: %s", command_to_send.strip())
                self._writer.write(command_to_send.encode())
                await self._writer.drain()
            except Exception as err:
                _LOGGER.error("Send failed: %s", err)
                # cleanup future
                if fut and not fut.done():
                    fut.set_exception(err)
                # close connection and raise so callers know
                await self._close_connection()
                raise

        # if caller didn't expect reply, return immediately
        if not fut:
            return None

        # wait for future outside the write lock
        try:
            return await asyncio.wait_for(fut, timeout=timeout)
        except asyncio.TimeoutError:
            _LOGGER.warning("Timeout waiting for reply to %s", command.strip())
            if not fut.done():
                fut.set_exception(asyncio.TimeoutError())
            raise

    async def ensure_connected(self, timeout: float = 5.0) -> None:
        """Wait until connected (or fail after timeout).

        If not connected, this will trigger a connect attempt.
        Uses a reconnect lock to avoid concurrent connect attempts.
        """
        if not self._connected_event.is_set():
            # start a connect if not already in progress
            async with self._reconnect_lock:
                # double check under lock
                if not self._connected_event.is_set():
                    # create background connect task attached to manager
                    if not self._manager_task or self._manager_task.done():
                        # if manager not running, start it
                        self._manager_task = asyncio.create_task(
                            self._manage_connection()
                        )
                    # If manager is already running, just wait for the connection event
                    # The manager will handle connection attempts with proper backoff
        try:
            await asyncio.wait_for(self._connected_event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            raise TimeoutError("Timeout waiting for connection")

    # ------------------------------------------------------------------ #
    # Connection Management
    # ------------------------------------------------------------------ #

    async def _manage_connection(self) -> None:
        """Keep the connection alive with reconnect/backoff.

        This manager will try to keep a connection open. It opens the connection
        and then waits for the listen task to exit (which happens on disconnect).
        If the listen task exits or open fails, it will retry with exponential
        backoff.
        """
        backoff = 1.0
        max_backoff = 60.0

        while not self._stopping:
            try:
                await self._open_connection()
                backoff = 1.0  # reset backoff
                if self._listen_task:
                    await self._listen_task  # normal exit when disconnected
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
        # avoid racing open if already connected
        if self._writer and not self._writer.is_closing():
            return
        _LOGGER.debug("Opening connection to %s:%s", self._host, self._port)
        try:
            self._reader, self._writer = await asyncio.open_connection(
                self._host, self._port
            )
        except Exception as err:
            # failed to connect — ensure state is clear and re-raise for manager to backoff
            self._connected_event.clear()
            _LOGGER.debug("Open connection failed: %s", err)
            raise

        self._connected_event.set()
        _LOGGER.info("Connected to Hegel at %s:%s", self._host, self._port)

        # cancel previous listen task if any (shouldn't normally be running)
        if self._listen_task and not self._listen_task.done():
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass

        self._listen_task = asyncio.create_task(self._listen_loop())

    async def _close_connection(self) -> None:
        """Close TCP connection and cleanup."""
        # clear event immediately so callers know we are disconnected
        self._connected_event.clear()

        # cancel listener and await it
        if self._listen_task:
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass
            self._listen_task = None

        # close writer
        if self._writer:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass

        self._reader = None
        self._writer = None

        # Fail all pending futures
        while self._pending:
            fut = self._pending.popleft()
            if not fut.done():
                try:
                    fut.set_exception(ConnectionError("Connection closed"))
                except Exception:
                    pass

    # ------------------------------------------------------------------ #
    # Listening / Routing
    # ------------------------------------------------------------------ #

    async def _listen_loop(self) -> None:
        """Background reader loop to handle both replies and push updates."""
        try:
            assert self._reader is not None
            while not self._reader.at_eof() and not self._stopping:
                try:
                    line = await self._reader.readuntil(separator=b"\r")
                except (
                    asyncio.IncompleteReadError,
                    ConnectionResetError,
                    OSError,
                ) as err:
                    # connection closed/RESET by peer — break and allow manager to reconnect
                    _LOGGER.error("Listen loop failed: %s", err)
                    break

                msg = line.decode(errors="ignore").strip()

                # If there is a pending future, fulfill the oldest one.
                handled = False
                if self._pending:
                    fut = self._pending.popleft()
                    if not fut.done():
                        fut.set_result(msg)
                        _LOGGER.debug("RX (reply): %s", msg)
                        handled = True

                # Push messages are delivered via callback
                if not handled:
                    _LOGGER.debug("RX (push): %s", msg)
                    if self._on_push:
                        try:
                            self._on_push(msg)
                        except Exception as err:
                            _LOGGER.error("Push callback failed: %s", err)

        except asyncio.CancelledError:
            # task cancelled — exit gracefully
            pass
        except Exception as err:
            _LOGGER.exception("Unexpected error in listen loop: %s", err)
        finally:
            # ensure connection closed and pending futures are failed
            await self._close_connection()
