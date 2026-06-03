"""Smoke tests for the in-process channel pair used by the testing plugin.

The real plugin path exercises the manager-side ``SandboxBridge`` and
needs the HA Core ``sandbox`` integration loaded — covered by
``tests/components/sandbox/test_testing_plugins.py`` on the core
side. These tests pin the lower-level pieces that live in
``hass_client`` and don't pull the integration: the loopback writer's
shape and the channel pair's call/response round-trip.
"""

import asyncio

from hass_client._proto import sandbox_pb2 as pb
from hass_client.messages import struct_to_dict
from hass_client.testing._inproc import _LoopbackWriter, make_inproc_channel_pair


async def test_loopback_writer_feeds_paired_reader() -> None:
    """Bytes written go straight into the paired reader."""
    reader = asyncio.StreamReader()
    writer = _LoopbackWriter(reader)
    writer.write(b"hello\n")
    # The reader has the bytes available without any loop iteration.
    line = await asyncio.wait_for(reader.readline(), timeout=0.1)
    assert line == b"hello\n"


async def test_loopback_writer_close_feeds_eof() -> None:
    """Closing the writer signals EOF to the paired reader."""
    reader = asyncio.StreamReader()
    writer = _LoopbackWriter(reader)
    writer.close()
    assert reader.at_eof()


async def test_loopback_writer_drain_is_noop() -> None:
    """``drain()`` resolves immediately — the loopback is unbuffered."""
    reader = asyncio.StreamReader()
    writer = _LoopbackWriter(reader)
    await writer.drain()
    await writer.wait_closed()


async def test_make_inproc_channel_pair_round_trips_a_call() -> None:
    """The two channels can call each other end-to-end without a process boundary.

    Uses a real registered message type (``store_load``) since the pair now
    speaks protobuf — the handler echoes the request key back so the
    round-trip is verified end-to-end.
    """
    mgr_channel, rt_channel = make_inproc_channel_pair(group="built-in")

    async def handler(payload: pb.StoreLoad) -> pb.StoreLoadResult:
        result = pb.StoreLoadResult()
        result.data.update({"echo": "ok", "saw": payload.key})
        return result

    rt_channel.register("sandbox/store_load", handler)
    rt_channel.start()
    mgr_channel.start()
    try:
        result = await asyncio.wait_for(
            mgr_channel.call("sandbox/store_load", pb.StoreLoad(key="hi")),
            timeout=2.0,
        )
        assert struct_to_dict(result.data) == {"echo": "ok", "saw": "hi"}
    finally:
        await mgr_channel.close()
        await rt_channel.close()
