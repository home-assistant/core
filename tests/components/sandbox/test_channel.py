"""Tests for the sandbox control :class:`Channel`."""

import asyncio

import pytest
import voluptuous as vol

from homeassistant.components.sandbox.channel import (
    Channel,
    ChannelClosedError,
    ChannelRemoteError,
)

from ._helpers import make_channel_pair


class _QueueTransport:
    """In-memory :class:`Transport` backed by a pair of queues.

    Stands in for a non-stream transport (the seam a future
    ``WebSocketTransport`` uses) so :meth:`Channel.from_transport` is
    exercised without any reader/writer pipe.
    """

    def __init__(
        self, inbox: asyncio.Queue[bytes | None], outbox: asyncio.Queue[bytes | None]
    ) -> None:
        self._inbox = inbox
        self._outbox = outbox
        self._closed = False

    async def read_frame(self) -> bytes | None:
        return await self._inbox.get()

    async def write_frame(self, data: bytes) -> None:
        self._outbox.put_nowait(data)

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            self._inbox.put_nowait(None)  # EOF sentinel for our reader

    async def wait_closed(self) -> None:
        return None


async def test_from_transport_round_trips() -> None:
    """A channel built over an arbitrary Transport dispatches normally."""
    q1: asyncio.Queue[bytes | None] = asyncio.Queue()
    q2: asyncio.Queue[bytes | None] = asyncio.Queue()
    channel_a = Channel.from_transport(_QueueTransport(q1, q2), name="a")
    channel_b = Channel.from_transport(_QueueTransport(q2, q1), name="b")
    channel_a.start()
    channel_b.start()

    async def echo(payload: object) -> dict[str, object]:
        return {"echoed": payload}

    channel_b.register("test/echo", echo)
    try:
        result = await asyncio.wait_for(channel_a.call("test/echo", 7), timeout=2.0)
        assert result == {"echoed": 7}
    finally:
        await channel_a.close()
        await channel_b.close()


@pytest.fixture(name="channels")
async def _channels_fixture() -> tuple:
    """Return a paired Channel + Channel, both started, both auto-cleaned."""
    channel_a, channel_b = make_channel_pair(use_json=True)
    channel_a.start()
    channel_b.start()
    yield channel_a, channel_b
    await channel_a.close()
    await channel_b.close()


async def test_round_trip_call(channels: tuple) -> None:
    """A call resolves with the remote handler's return value."""
    channel_a, channel_b = channels

    async def echo(payload: dict) -> dict:
        return {"echoed": payload["value"]}

    channel_b.register("test/echo", echo)
    result = await channel_a.call("test/echo", {"value": 42})
    assert result == {"echoed": 42}


async def test_remote_error_surfaces_as_exception(channels: tuple) -> None:
    """A handler that raises sends an error response that the caller raises."""
    channel_a, channel_b = channels

    async def boom(_payload: object) -> None:
        raise ValueError("kaboom")

    channel_b.register("test/boom", boom)
    with pytest.raises(ChannelRemoteError) as exc:
        await channel_a.call("test/boom", None)
    assert "kaboom" in str(exc.value)
    assert exc.value.error_type == "ValueError"


async def test_vol_invalid_carries_error_data(channels: tuple) -> None:
    """A handler raising ``vol.Invalid`` ships its path in ``error_data``."""
    channel_a, channel_b = channels

    async def bad(_payload: object) -> None:
        raise vol.Invalid("expected int", path=["options", "count"])

    channel_b.register("test/bad", bad)
    with pytest.raises(ChannelRemoteError) as exc:
        await channel_a.call("test/bad", None)
    assert exc.value.error_type == "Invalid"
    assert exc.value.error_data == {
        "kind": "invalid",
        "msg": "expected int",
        "path": ["options", "count"],
    }


async def test_vol_multiple_invalid_round_trips_children(channels: tuple) -> None:
    """A ``vol.MultipleInvalid`` ships each child error in ``error_data``."""
    channel_a, channel_b = channels

    async def bad(_payload: object) -> None:
        raise vol.MultipleInvalid(
            [
                vol.Invalid("expected int", path=["count"]),
                vol.Invalid("required key", path=["name"]),
            ]
        )

    channel_b.register("test/multi", bad)
    with pytest.raises(ChannelRemoteError) as exc:
        await channel_a.call("test/multi", None)
    assert exc.value.error_type == "MultipleInvalid"
    assert exc.value.error_data == {
        "kind": "multiple",
        "errors": [
            {"kind": "invalid", "msg": "expected int", "path": ["count"]},
            {"kind": "invalid", "msg": "required key", "path": ["name"]},
        ],
    }


async def test_unknown_handler_returns_error(channels: tuple) -> None:
    """Calls to unregistered types come back as remote errors."""
    channel_a, _ = channels
    with pytest.raises(ChannelRemoteError) as exc:
        await channel_a.call("test/unknown", None)
    assert exc.value.error_type == "ChannelUnknownType"


async def test_close_cancels_inflight_calls(channels: tuple) -> None:
    """Closing the channel mid-call surfaces ChannelClosedError to the caller."""
    channel_a, channel_b = channels

    received = asyncio.Event()

    async def slow(_payload: object) -> None:
        received.set()
        await asyncio.sleep(60)

    channel_b.register("test/slow", slow)
    call_task = asyncio.create_task(channel_a.call("test/slow", None))
    await received.wait()
    await channel_a.close()

    with pytest.raises(ChannelClosedError):
        await call_task


async def test_push_message_is_one_way(channels: tuple) -> None:
    """Push messages run the handler but produce no reply."""
    channel_a, channel_b = channels
    received: list[object] = []

    async def receive(payload: object) -> None:
        received.append(payload)

    channel_b.register("test/push", receive)
    await channel_a.push("test/push", {"hello": "world"})

    for _ in range(100):
        if received:
            break
        await asyncio.sleep(0.01)
    assert received == [{"hello": "world"}]


async def test_handler_can_call_back_without_deadlock(channels: tuple) -> None:
    """A handler that issues channel.call mid-execution doesn't deadlock.

    Phase 12: dispatch runs in a task so the reader keeps draining the
    wire — the nested call's reply can be picked up while the outer
    handler is still suspended.
    """
    channel_a, channel_b = channels

    async def a_ping(_payload: object) -> dict[str, bool]:
        return {"pong": True}

    async def b_forward(_payload: object) -> dict[str, bool]:
        # Re-enter the channel: B's handler issues a call back to A
        # while B's reader is the same task that dispatched us.
        return await channel_b.call("a/ping", None, timeout=2.0)

    channel_a.register("a/ping", a_ping)
    channel_b.register("b/forward", b_forward)

    result = await asyncio.wait_for(channel_a.call("b/forward", None), timeout=2.0)
    assert result == {"pong": True}


async def test_concurrency_cap_queues_excess_handlers() -> None:
    """The (cap+1)th call queues at the semaphore until a slot frees.

    Sets a tiny ``max_inflight`` so the test fires (cap+1) slow handlers
    and observes the last one waiting until one of the first two
    finishes.
    """
    channel_a, channel_b = make_channel_pair(max_inflight_b=2, use_json=True)
    channel_a.start()
    channel_b.start()
    started: list[asyncio.Event] = [asyncio.Event() for _ in range(3)]
    release: list[asyncio.Event] = [asyncio.Event() for _ in range(3)]

    async def slow(payload: dict) -> int:
        idx = payload["idx"]
        started[idx].set()
        await release[idx].wait()
        return idx

    channel_b.register("test/slow", slow)

    try:
        tasks = [
            asyncio.create_task(channel_a.call("test/slow", {"idx": i}))
            for i in range(3)
        ]

        # First two enter the handler; the third queues at the semaphore.
        await asyncio.wait_for(started[0].wait(), timeout=2.0)
        await asyncio.wait_for(started[1].wait(), timeout=2.0)
        await asyncio.sleep(0.05)
        assert not started[2].is_set()

        # Release the first; the third can now enter.
        release[0].set()
        await asyncio.wait_for(started[2].wait(), timeout=2.0)

        # Release the rest and confirm all three replies land.
        release[1].set()
        release[2].set()
        results = await asyncio.wait_for(asyncio.gather(*tasks), timeout=2.0)
        assert sorted(results) == [0, 1, 2]
    finally:
        await channel_a.close()
        await channel_b.close()
