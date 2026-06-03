"""Sandbox-side mirror of ``homeassistant.components.sandbox_v2.channel``.

Kept as a stand-alone module to honour the project boundary: the HA Core
integration must not import from ``hass_client`` at integration-load time,
and ``hass_client`` does not pull from ``homeassistant.components.*``. The
two files speak the same wire format — see the docstring on the HA side
for the layering (Channel / Codec / Transport) and the :class:`Frame`
shape.

Inbound calls and pushes are dispatched in their own tasks so a handler
that itself issues :meth:`Channel.call` does not block the reader — the
reply for the nested call has to come back through the same reader. A
bounded semaphore caps how many handlers can run concurrently; the N+1th
inbound message queues at the semaphore (not at the reader) until a slot
frees up.
"""

import asyncio
from collections.abc import Awaitable, Callable, Coroutine
import contextlib
from dataclasses import dataclass, field
from enum import StrEnum
import json
import logging
import struct
from typing import Any, Protocol

import voluptuous as vol

_LOGGER = logging.getLogger(__name__)

Handler = Callable[[Any], Awaitable[Any]]

DEFAULT_MAX_INFLIGHT = 16

# Hard cap on a single frame's body. A length prefix larger than this aborts
# the channel rather than letting a compromised peer allocate the process to
# death.
MAX_FRAME_SIZE = 16 * 1024 * 1024

_LENGTH_PREFIX = struct.Struct(">I")


def _serialize_invalid(err: vol.Invalid) -> dict[str, Any]:
    """Capture a ``vol.Invalid``'s message + path so main can rebuild it.

    Path parts may be ``vol.Marker``s or other non-JSON objects, so each
    part is stringified.
    """
    return {
        "kind": "invalid",
        "msg": err.error_message,
        "path": [str(part) for part in (err.path or [])],
    }


def error_data_for(err: BaseException) -> dict[str, Any] | None:
    """Structured payload that lets main reconstruct a voluptuous error.

    ``MultipleInvalid`` is a subclass of ``Invalid``, so it is checked first.
    Returns ``None`` for anything that is not a voluptuous error.
    """
    if isinstance(err, vol.MultipleInvalid):
        return {
            "kind": "multiple",
            "errors": [_serialize_invalid(child) for child in err.errors],
        }
    if isinstance(err, vol.Invalid):
        return _serialize_invalid(err)
    return None


class FrameKind(StrEnum):
    """Which of the three wire shapes a :class:`Frame` carries."""

    CALL = "call"
    PUSH = "push"
    RESPONSE = "response"


@dataclass(slots=True)
class Frame:
    """Transport/codec-neutral representation of one wire message."""

    kind: FrameKind
    id: int = 0
    type: str = ""
    payload: Any = None
    ok: bool = False
    result: Any = None
    error: str | None = None
    error_type: str | None = None
    error_data: dict[str, Any] | None = field(default=None)

    @classmethod
    def call(cls, call_id: int, msg_type: str, payload: Any) -> Frame:
        """Build a request frame that expects a reply."""
        return cls(FrameKind.CALL, id=call_id, type=msg_type, payload=payload)

    @classmethod
    def push(cls, msg_type: str, payload: Any) -> Frame:
        """Build a one-way push frame."""
        return cls(FrameKind.PUSH, id=0, type=msg_type, payload=payload)

    @classmethod
    def ok_response(cls, call_id: int, result: Any, msg_type: str = "") -> Frame:
        """Build a success response frame.

        ``msg_type`` is carried so a stateless codec (the protobuf one) can
        look up the result message class on encode + decode.
        """
        return cls(
            FrameKind.RESPONSE, id=call_id, type=msg_type, ok=True, result=result
        )

    @classmethod
    def error_response(
        cls,
        call_id: int,
        error: str,
        error_type: str | None,
        error_data: dict[str, Any] | None = None,
        msg_type: str = "",
    ) -> Frame:
        """Build a failure response frame."""
        return cls(
            FrameKind.RESPONSE,
            id=call_id,
            type=msg_type,
            ok=False,
            error=error,
            error_type=error_type,
            error_data=error_data,
        )


class Codec(Protocol):
    """Serialises a :class:`Frame` to bytes and back."""

    def encode(self, frame: Frame) -> bytes:
        """Return the wire bytes for ``frame``."""

    def decode(self, data: bytes) -> Frame:
        """Rebuild a :class:`Frame` from wire bytes."""


class JsonCodec:
    """One-JSON-object-per-frame codec.

    Line-compatible with the original wire shape (sans the trailing
    newline, which the length prefix replaces). Kept as the default for
    tests and debugging; production rides :class:`ProtobufCodec`.
    """

    def encode(self, frame: Frame) -> bytes:
        """Encode a frame to a compact JSON object."""
        message: dict[str, Any]
        if frame.kind is FrameKind.CALL:
            message = {"id": frame.id, "type": frame.type, "payload": frame.payload}
        elif frame.kind is FrameKind.PUSH:
            message = {"type": frame.type, "payload": frame.payload}
        elif frame.ok:
            message = {"id": frame.id, "ok": True, "result": frame.result}
        else:
            message = {
                "id": frame.id,
                "ok": False,
                "error": frame.error,
                "error_type": frame.error_type,
            }
            if frame.error_data is not None:
                message["error_data"] = frame.error_data
        return json.dumps(message, separators=(",", ":")).encode("utf-8")

    def decode(self, data: bytes) -> Frame:
        """Decode a JSON object into a frame, inferring the kind from keys."""
        message = json.loads(data)
        has_id = "id" in message
        has_type = "type" in message
        if has_id and not has_type:
            # Response to a call we sent out.
            if message.get("ok"):
                return Frame.ok_response(message["id"], message.get("result"))
            return Frame.error_response(
                message["id"],
                message.get("error", "unknown error"),
                message.get("error_type"),
                message.get("error_data"),
            )
        if not has_id:
            return Frame.push(message.get("type", ""), message.get("payload"))
        return Frame.call(message["id"], message["type"], message.get("payload"))


class Transport(Protocol):
    """Moves whole frame blobs over some byte channel."""

    async def read_frame(self) -> bytes | None:
        """Return the next frame's bytes, or ``None`` at end-of-stream."""

    async def write_frame(self, data: bytes) -> None:
        """Write one frame's bytes."""

    def close(self) -> None:
        """Begin closing the underlying channel."""

    async def wait_closed(self) -> None:
        """Wait for the underlying channel to finish closing."""


class FrameTooLargeError(Exception):
    """A peer announced a frame larger than :data:`MAX_FRAME_SIZE`."""


class StreamTransport:
    """Length-prefixed framing over a reader/writer pair.

    Each frame is a 4-byte big-endian length followed by exactly that many
    body bytes. Used for stdio and unix-socket connections.
    """

    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        """Wrap a reader/writer pair with length-prefixed framing."""
        self._reader = reader
        self._writer = writer

    async def read_frame(self) -> bytes | None:
        """Read one length-prefixed frame, or ``None`` at clean EOF."""
        try:
            header = await self._reader.readexactly(_LENGTH_PREFIX.size)
        except asyncio.IncompleteReadError:
            return None
        (length,) = _LENGTH_PREFIX.unpack(header)
        if length > MAX_FRAME_SIZE:
            raise FrameTooLargeError(
                f"frame length {length} exceeds cap {MAX_FRAME_SIZE}"
            )
        try:
            return await self._reader.readexactly(length)
        except asyncio.IncompleteReadError:
            return None

    async def write_frame(self, data: bytes) -> None:
        """Write one length-prefixed frame and flush it."""
        self._writer.write(_LENGTH_PREFIX.pack(len(data)) + data)
        await self._writer.drain()

    def close(self) -> None:
        """Close the writer side of the connection."""
        self._writer.close()

    async def wait_closed(self) -> None:
        """Wait for the writer to finish closing."""
        await self._writer.wait_closed()


class ChannelClosedError(Exception):
    """Raised when an operation is attempted on a closed channel."""


class ChannelRemoteError(Exception):
    """Raised when the remote side returns an error response."""

    def __init__(
        self,
        error: str,
        error_type: str | None = None,
        error_data: dict[str, Any] | None = None,
    ) -> None:
        """Initialise with the remote error message and exception class name.

        ``error_data`` carries a structured payload (set for voluptuous
        errors) so the receiver can rebuild the original exception shape.
        """
        super().__init__(error)
        self.error = error
        self.error_type = error_type
        self.error_data = error_data


class Channel:
    """One bidirectional request/response channel over a transport + codec."""

    def __init__(
        self,
        reader: asyncio.StreamReader | None = None,
        writer: asyncio.StreamWriter | None = None,
        *,
        transport: Transport | None = None,
        codec: Codec | None = None,
        name: str = "channel",
        max_inflight: int = DEFAULT_MAX_INFLIGHT,
    ) -> None:
        """Wrap a reader/writer pair (or a transport) into a channel.

        The common case passes a ``reader``/``writer`` pair, framed with
        :class:`StreamTransport` (length-prefixed). To run over a non-stream
        transport (e.g. websockets), pass ``transport=`` instead — see
        :meth:`from_transport`.

        ``codec`` defaults to :class:`JsonCodec`. ``max_inflight`` bounds how
        many handler tasks may run at once. Once the cap is reached, the read
        loop keeps draining the wire but newly-spawned handlers wait on the
        semaphore until a slot frees up — so a misbehaving integration can't
        starve the reader by fanning out unbounded inbound work.
        """
        if transport is None:
            if reader is None or writer is None:
                raise TypeError("Channel needs a reader/writer pair or a transport")
            transport = StreamTransport(reader, writer)
        self._transport: Transport = transport
        self._codec: Codec = codec if codec is not None else JsonCodec()
        self._name = name
        self._next_id = 1
        self._pending: dict[int, asyncio.Future[Any]] = {}
        self._handlers: dict[str, Handler] = {}
        self._reader_task: asyncio.Task[None] | None = None
        self._closed: bool = False
        self._write_lock = asyncio.Lock()
        self._inflight: set[asyncio.Task[None]] = set()
        self._inflight_sem = asyncio.Semaphore(max_inflight)

    @classmethod
    def from_transport(
        cls,
        transport: Transport,
        *,
        codec: Codec | None = None,
        name: str = "channel",
        max_inflight: int = DEFAULT_MAX_INFLIGHT,
    ) -> Channel:
        """Build a channel over an arbitrary :class:`Transport`.

        This is the seam a future ``WebSocketTransport`` drops into — the
        dispatch core is identical regardless of how frames reach the wire.
        """
        return cls(
            transport=transport, codec=codec, name=name, max_inflight=max_inflight
        )

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
            await self._write(Frame.call(call_id, msg_type, payload))
            if timeout is None:
                return await future
            return await asyncio.wait_for(future, timeout=timeout)
        finally:
            self._pending.pop(call_id, None)

    async def push(self, msg_type: str, payload: Any = None) -> None:
        """Send a one-way push message; the remote does not reply."""
        if self._closed:
            raise ChannelClosedError(f"channel {self._name!r} is closed")
        await self._write(Frame.push(msg_type, payload))

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
            self._transport.close()
            with contextlib.suppress(asyncio.CancelledError):
                await self._transport.wait_closed()
        if self._reader_task is not None:
            self._reader_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._reader_task
            self._reader_task = None
        if inflight:
            await asyncio.gather(*inflight, return_exceptions=True)

    async def _write(self, frame: Frame) -> None:
        data = self._codec.encode(frame)
        async with self._write_lock:
            await self._transport.write_frame(data)

    async def _read_loop(self) -> None:
        try:
            while True:
                try:
                    data = await self._transport.read_frame()
                except FrameTooLargeError as err:
                    _LOGGER.error("channel %s: %s; aborting channel", self._name, err)
                    return
                if data is None:
                    return
                try:
                    frame = self._codec.decode(data)
                except Exception:  # noqa: BLE001
                    _LOGGER.warning(
                        "channel %s: dropping undecodable frame (%d bytes)",
                        self._name,
                        len(data),
                    )
                    continue
                self._dispatch(frame)
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
                            ChannelClosedError(f"channel {self._name!r} stream ended")
                        )
                self._pending.clear()
                for task in list(self._inflight):
                    task.cancel()

    def _dispatch(self, frame: Frame) -> None:
        """Route an inbound frame; non-blocking — handlers run in tasks."""
        if frame.kind is FrameKind.RESPONSE:
            future = self._pending.get(frame.id)
            if future is None or future.done():
                return
            if frame.ok:
                future.set_result(frame.result)
            else:
                future.set_exception(
                    ChannelRemoteError(
                        frame.error or "unknown error",
                        frame.error_type,
                        frame.error_data,
                    )
                )
            return

        handler = self._handlers.get(frame.type)

        if frame.kind is FrameKind.PUSH:
            if handler is not None:
                self._spawn_handler(
                    self._run_push_handler(frame.type, handler, frame.payload)
                )
            return

        if handler is None:
            self._spawn_handler(
                self._write(
                    Frame.error_response(
                        frame.id,
                        f"no handler for {frame.type!r}",
                        "ChannelUnknownType",
                        msg_type=frame.type,
                    )
                )
            )
            return

        self._spawn_handler(
            self._run_call_handler(frame.id, frame.type, handler, frame.payload)
        )

    def _spawn_handler(self, coro: Coroutine[Any, Any, Any]) -> None:
        """Start a handler task and track it for cancellation on close."""
        task = asyncio.create_task(coro, name=f"sandbox_v2[{self._name}]:dispatch")
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
                frame = Frame.error_response(
                    call_id,
                    str(err) or err.__class__.__name__,
                    err.__class__.__name__,
                    error_data_for(err),
                    msg_type=msg_type,
                )
                with contextlib.suppress(Exception):
                    await self._write(frame)
                return
            if self._closed:
                return
            with contextlib.suppress(Exception):
                await self._write(Frame.ok_response(call_id, result, msg_type))


__all__ = [
    "Channel",
    "ChannelClosedError",
    "ChannelRemoteError",
    "Codec",
    "Frame",
    "FrameKind",
    "FrameTooLargeError",
    "Handler",
    "JsonCodec",
    "StreamTransport",
    "Transport",
    "error_data_for",
]
