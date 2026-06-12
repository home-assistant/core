"""Shared helpers for sandbox tests.

Provides:

* :func:`make_channel_pair` — two :class:`Channel` instances joined by an
  in-memory bytes transport. Each writer feeds the other reader.
* :class:`FakeSandboxProcess` — a stand-in for
  :class:`homeassistant.components.sandbox.manager.SandboxProcess` that
  exposes a pre-built channel without ever spawning a subprocess.
* :class:`FakeSandboxManager` — minimal stand-in for
  :class:`SandboxManager` that just returns FakeSandboxProcess instances.
* :class:`JsonCodec` — registry-free channel-core test/debug codec, kept out
  of the production :mod:`channel` module so a missing ``codec=`` fails loudly.
"""

import asyncio
import json
from typing import Any

from homeassistant.components.sandbox.channel import Channel, Frame, FrameKind
from homeassistant.components.sandbox.codec_protobuf import ProtobufCodec


class JsonCodec:
    """Registry-free one-JSON-object-per-frame codec for channel-core tests.

    The production wire is :class:`ProtobufCodec`. This codec lived in
    :mod:`homeassistant.components.sandbox.channel` until it was moved here:
    keeping it out of the channel module means a ``Channel`` built without an
    explicit ``codec=`` is a construction-time error instead of silently
    speaking JSON at a protobuf peer. It passes frame payloads through as plain
    JSON (no ``type``-to-proto lookup), so the concurrency-critical channel core
    can be exercised with synthetic message types and arbitrary dict/int
    payloads.
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


class _LoopbackWriter:
    """Async writer that pushes bytes straight into a paired StreamReader."""

    def __init__(self, target: asyncio.StreamReader) -> None:
        self._target = target
        self._closed = False

    def write(self, data: bytes) -> None:
        if self._closed:
            return
        self._target.feed_data(data)

    async def drain(self) -> None:
        return None

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._target.feed_eof()

    async def wait_closed(self) -> None:
        return None


def make_channel_pair(
    *,
    name_a: str = "a",
    name_b: str = "b",
    max_inflight_a: int | None = None,
    max_inflight_b: int | None = None,
    max_queued_a: int | None = None,
    max_queued_b: int | None = None,
    use_json: bool = False,
) -> tuple[Channel, Channel]:
    """Return two channels connected to each other in-memory.

    ``max_inflight_a`` / ``max_inflight_b`` override the per-side handler
    concurrency cap; ``max_queued_a`` / ``max_queued_b`` override the per-side
    inflight (queued + running) shed cap. Both default to the channel's own
    defaults. Useful for exercising the bounded-semaphore and read-backpressure
    paths.

    The pair speaks protobuf by default (production parity, so real
    handlers receive typed messages). ``use_json=True`` falls back to the
    registry-free :class:`JsonCodec` for channel-core tests that drive
    synthetic message types with plain dict payloads.
    """
    reader_a = asyncio.StreamReader()
    reader_b = asyncio.StreamReader()
    writer_a = _LoopbackWriter(reader_b)  # a's writes → b's reader
    writer_b = _LoopbackWriter(reader_a)
    kwargs_a: dict[str, int] = {}
    kwargs_b: dict[str, int] = {}
    if max_inflight_a is not None:
        kwargs_a["max_inflight"] = max_inflight_a
    if max_inflight_b is not None:
        kwargs_b["max_inflight"] = max_inflight_b
    if max_queued_a is not None:
        kwargs_a["max_queued"] = max_queued_a
    if max_queued_b is not None:
        kwargs_b["max_queued"] = max_queued_b
    codec_a = JsonCodec() if use_json else ProtobufCodec()
    codec_b = JsonCodec() if use_json else ProtobufCodec()
    channel_a = Channel(reader_a, writer_a, name=name_a, codec=codec_a, **kwargs_a)  # type: ignore[arg-type]
    channel_b = Channel(reader_b, writer_b, name=name_b, codec=codec_b, **kwargs_b)  # type: ignore[arg-type]
    return channel_a, channel_b


class FakeSandboxProcess:
    """Stand-in for :class:`SandboxProcess` that wraps a single channel."""

    def __init__(self, group: str, channel: Channel) -> None:
        self.group = group
        self._channel = channel
        self.state = "running"

    @property
    def channel(self) -> Channel:
        return self._channel


class FakeSandboxManager:
    """Stand-in for :class:`SandboxManager` returning FakeSandboxProcess."""

    def __init__(self) -> None:
        self._sandboxes: dict[str, FakeSandboxProcess] = {}
        self.start_calls: list[str] = []

    def install(self, group: str, channel: Channel) -> FakeSandboxProcess:
        """Register a channel under ``group`` and return the fake process."""
        process = FakeSandboxProcess(group, channel)
        self._sandboxes[group] = process
        return process

    async def ensure_started(self, group: str) -> FakeSandboxProcess:
        self.start_calls.append(group)
        process = self._sandboxes.get(group)
        if process is None:
            raise RuntimeError(f"FakeSandboxManager: no channel for {group!r}")
        return process

    def get(self, group: str) -> FakeSandboxProcess | None:
        return self._sandboxes.get(group)
