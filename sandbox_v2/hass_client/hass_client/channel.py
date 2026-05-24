"""Sandbox-side mirror of ``homeassistant.components.sandbox_v2.channel``.

Kept as a stand-alone module to honour the project boundary: the HA Core
integration must not import from ``hass_client`` at integration-load time,
and ``hass_client`` does not pull from ``homeassistant.components.*``. The
two files speak the same wire format — see the docstring on the HA side
for the message schema.

Inbound calls and pushes are dispatched in their own tasks so a handler that
itself issues :meth:`Channel.call` does not block the reader — the reply for
the nested call has to come back through the same reader. A bounded
semaphore caps how many handlers can run concurrently; the N+1th inbound
message queues at the semaphore (not at the reader) until a slot frees up.
"""

import asyncio
from collections.abc import Awaitable, Callable, Coroutine
import contextlib
import json
import logging
from typing import Any

_LOGGER = logging.getLogger(__name__)

Handler = Callable[[Any], Awaitable[Any]]

DEFAULT_MAX_INFLIGHT = 16


class ChannelClosedError(Exception):
    """Raised when an operation is attempted on a closed channel."""


class ChannelRemoteError(Exception):
    """Raised when the remote side returns an error response."""

    def __init__(self, error: str, error_type: str | None = None) -> None:
        """Initialise with the remote error message and exception class name."""
        super().__init__(error)
        self.error = error
        self.error_type = error_type


class Channel:
    """One bidirectional request/response channel over a line-oriented stream."""

    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        *,
        name: str = "channel",
        max_inflight: int = DEFAULT_MAX_INFLIGHT,
    ) -> None:
        """Wrap a reader/writer pair into a request/response channel.

        ``max_inflight`` bounds how many handler tasks may run at once.
        Once the cap is reached, the read loop keeps draining the wire
        but newly-spawned handlers wait on the semaphore until a slot
        frees up — so a misbehaving integration can't starve the reader
        by fanning out unbounded inbound work.
        """
        self._reader = reader
        self._writer = writer
        self._name = name
        self._next_id = 1
        self._pending: dict[int, asyncio.Future[Any]] = {}
        self._handlers: dict[str, Handler] = {}
        self._reader_task: asyncio.Task[None] | None = None
        self._closed: bool = False
        self._write_lock = asyncio.Lock()
        self._inflight: set[asyncio.Task[None]] = set()
        self._inflight_sem = asyncio.Semaphore(max_inflight)

    @property
    def closed(self) -> bool:
        """Return True once the channel has been closed."""
        return self._closed

    def register(self, msg_type: str, handler: Handler) -> None:
        """Register an async handler for inbound calls of this type."""
        self._handlers[msg_type] = handler

    def start(self) -> None:
        """Begin reading messages off the wire."""
        if self._reader_task is not None:
            return
        self._reader_task = asyncio.create_task(
            self._read_loop(), name=f"sandbox_v2[{self._name}]:reader"
        )

    async def call(
        self, msg_type: str, payload: Any = None, *, timeout: float | None = None
    ) -> Any:
        """Send a request and await its response."""
        if self._closed:
            raise ChannelClosedError(f"channel {self._name!r} is closed")
        call_id = self._next_id
        self._next_id += 1
        future: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
        self._pending[call_id] = future
        try:
            await self._write({"id": call_id, "type": msg_type, "payload": payload})
            if timeout is None:
                return await future
            return await asyncio.wait_for(future, timeout=timeout)
        finally:
            self._pending.pop(call_id, None)

    async def push(self, msg_type: str, payload: Any = None) -> None:
        """Send a one-way push message; the remote does not reply."""
        if self._closed:
            raise ChannelClosedError(f"channel {self._name!r} is closed")
        await self._write({"type": msg_type, "payload": payload})

    async def close(self) -> None:
        """Close the channel and cancel any in-flight calls."""
        if self._closed:
            return
        self._closed = True
        for future in self._pending.values():
            if not future.done():
                future.set_exception(
                    ChannelClosedError(f"channel {self._name!r} is closed")
                )
        self._pending.clear()
        inflight = list(self._inflight)
        for task in inflight:
            task.cancel()
        with contextlib.suppress(Exception):
            self._writer.close()
            with contextlib.suppress(asyncio.CancelledError):
                await self._writer.wait_closed()
        if self._reader_task is not None:
            self._reader_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._reader_task
            self._reader_task = None
        if inflight:
            await asyncio.gather(*inflight, return_exceptions=True)

    async def _write(self, message: dict[str, Any]) -> None:
        line = json.dumps(message, separators=(",", ":")).encode("utf-8") + b"\n"
        async with self._write_lock:
            self._writer.write(line)
            await self._writer.drain()

    async def _read_loop(self) -> None:
        try:
            while True:
                line = await self._reader.readline()
                if not line:
                    return
                try:
                    message = json.loads(line)
                except json.JSONDecodeError:
                    _LOGGER.warning(
                        "channel %s: dropping malformed line %r", self._name, line
                    )
                    continue
                self._dispatch(message)
        except asyncio.CancelledError:
            raise
        except Exception:
            _LOGGER.exception("channel %s: read loop crashed", self._name)
        finally:
            if not self._closed:
                self._closed = True
                for future in self._pending.values():
                    if not future.done():
                        future.set_exception(
                            ChannelClosedError(
                                f"channel {self._name!r} stream ended"
                            )
                        )
                self._pending.clear()
                for task in list(self._inflight):
                    task.cancel()

    def _dispatch(self, message: dict[str, Any]) -> None:
        """Route an inbound message; non-blocking — handlers run in tasks."""
        if "id" in message and "type" not in message:
            call_id = message["id"]
            future = self._pending.get(call_id)
            if future is None or future.done():
                return
            if message.get("ok"):
                future.set_result(message.get("result"))
            else:
                future.set_exception(
                    ChannelRemoteError(
                        message.get("error", "unknown error"),
                        message.get("error_type"),
                    )
                )
            return

        msg_type = message.get("type")
        if msg_type is None:
            return
        handler = self._handlers.get(msg_type)
        payload = message.get("payload")

        if "id" not in message:
            if handler is not None:
                self._spawn_handler(
                    self._run_push_handler(msg_type, handler, payload)
                )
            return

        call_id = message["id"]
        if handler is None:
            self._spawn_handler(
                self._write(
                    {
                        "id": call_id,
                        "ok": False,
                        "error": f"no handler for {msg_type!r}",
                        "error_type": "ChannelUnknownType",
                    }
                )
            )
            return

        self._spawn_handler(
            self._run_call_handler(call_id, msg_type, handler, payload)
        )

    def _spawn_handler(self, coro: Coroutine[Any, Any, Any]) -> None:
        """Start a handler task and track it for cancellation on close."""
        task = asyncio.create_task(
            coro, name=f"sandbox_v2[{self._name}]:dispatch"
        )
        self._inflight.add(task)
        task.add_done_callback(self._inflight.discard)

    async def _run_push_handler(
        self, msg_type: str, handler: Handler, payload: Any
    ) -> None:
        """Run a push handler under the inflight cap; swallow exceptions."""
        async with self._inflight_sem:
            try:
                await handler(payload)
            except asyncio.CancelledError:
                raise
            except Exception:
                _LOGGER.exception(
                    "channel %s: push handler for %s raised",
                    self._name,
                    msg_type,
                )

    async def _run_call_handler(
        self,
        call_id: int,
        msg_type: str,
        handler: Handler,
        payload: Any,
    ) -> None:
        """Run a call handler under the inflight cap and write its reply."""
        async with self._inflight_sem:
            try:
                result = await handler(payload)
            except asyncio.CancelledError:
                raise
            except Exception as err:  # noqa: BLE001
                if self._closed:
                    return
                with contextlib.suppress(Exception):
                    await self._write(
                        {
                            "id": call_id,
                            "ok": False,
                            "error": str(err) or err.__class__.__name__,
                            "error_type": err.__class__.__name__,
                        }
                    )
                return
            if self._closed:
                return
            with contextlib.suppress(Exception):
                await self._write(
                    {"id": call_id, "ok": True, "result": result}
                )


__all__ = [
    "Channel",
    "ChannelClosedError",
    "ChannelRemoteError",
    "Handler",
]
