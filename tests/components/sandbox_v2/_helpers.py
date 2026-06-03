"""Shared helpers for Phase 4 sandbox_v2 tests.

Provides:

* :func:`make_channel_pair` — two :class:`Channel` instances joined by an
  in-memory bytes transport. Each writer feeds the other reader.
* :class:`FakeSandboxProcess` — a stand-in for
  :class:`homeassistant.components.sandbox_v2.manager.SandboxProcess` that
  exposes a pre-built channel without ever spawning a subprocess.
* :class:`FakeSandboxManager` — minimal stand-in for
  :class:`SandboxManager` that just returns FakeSandboxProcess instances.
"""

import asyncio

from homeassistant.components.sandbox_v2.channel import Channel, JsonCodec
from homeassistant.components.sandbox_v2.codec_protobuf import ProtobufCodec


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
    use_json: bool = False,
) -> tuple[Channel, Channel]:
    """Return two channels connected to each other in-memory.

    ``max_inflight_a`` / ``max_inflight_b`` override the per-side
    handler concurrency cap when set; otherwise the channel's default
    applies. Useful for exercising the bounded-semaphore path.

    The pair speaks protobuf by default (production parity, so real
    handlers receive typed messages). ``use_json=True`` falls back to the
    registry-free :class:`JsonCodec` for channel-core tests that drive
    synthetic message types with plain dict payloads.
    """
    reader_a = asyncio.StreamReader()
    reader_b = asyncio.StreamReader()
    writer_a = _LoopbackWriter(reader_b)  # a's writes → b's reader
    writer_b = _LoopbackWriter(reader_a)
    kwargs_a: dict[str, int] = (
        {"max_inflight": max_inflight_a} if max_inflight_a is not None else {}
    )
    kwargs_b: dict[str, int] = (
        {"max_inflight": max_inflight_b} if max_inflight_b is not None else {}
    )
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
