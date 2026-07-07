"""Tests for :class:`hass_client.event_mirror.EventMirror`."""

import asyncio
import tempfile
from typing import Any

from hass_client._proto import sandbox_pb2 as pb
from hass_client.approved_domains import ApprovedDomains
from hass_client.channel import Channel
from hass_client.codec_protobuf import ProtobufCodec
from hass_client.event_mirror import EventMirror
from hass_client.flow_runner import FlowRunner
from hass_client.messages import decode_json_dict
import pytest


class _LoopbackWriter:
    def __init__(self, target: asyncio.StreamReader) -> None:
        self._target = target

    def write(self, data: bytes) -> None:
        self._target.feed_data(data)

    async def drain(self) -> None:
        return None

    def close(self) -> None:
        self._target.feed_eof()

    async def wait_closed(self) -> None:
        return None


def _make_channel_pair() -> tuple[Channel, Channel]:
    reader_a = asyncio.StreamReader()
    reader_b = asyncio.StreamReader()
    return (
        Channel(
            reader_a, _LoopbackWriter(reader_b), name="main", codec=ProtobufCodec()
        ),  # type: ignore[arg-type]
        Channel(
            reader_b, _LoopbackWriter(reader_a), name="sandbox", codec=ProtobufCodec()
        ),  # type: ignore[arg-type]
    )


@pytest.fixture(name="channels")
async def _channels_fixture() -> tuple[Channel, Channel]:
    main, sandbox = _make_channel_pair()
    yield main, sandbox
    await main.close()
    await sandbox.close()


@pytest.fixture(name="hass_runtime")
async def _hass_runtime_fixture():
    with tempfile.TemporaryDirectory(prefix="sandbox_event_mirror_") as tmp:
        flow_runner = await FlowRunner.create(config_dir=tmp)
        try:
            yield flow_runner.hass
        finally:
            await flow_runner.async_stop()


async def _wait_until(predicate, *, ticks: int = 50) -> None:
    for _ in range(ticks):
        if predicate():
            return
        await asyncio.sleep(0)


async def test_owned_domain_event_is_forwarded(
    channels: tuple[Channel, Channel], hass_runtime: Any
) -> None:
    """``zha_event`` reaches main when ``zha`` is approved."""
    main, sandbox = channels
    forwarded: list[pb.FireEvent] = []

    async def _on_fire(msg: pb.FireEvent) -> None:
        forwarded.append(msg)

    main.register("sandbox/fire_event", _on_fire)
    main.start()
    sandbox.start()

    approved = ApprovedDomains(["zha"])
    mirror = EventMirror(hass_runtime, approved)
    mirror.register(sandbox)

    hass_runtime.bus.async_fire(
        "zha_event", {"command": "on", "device_ieee": "00:11:22:33:44"}
    )
    await _wait_until(lambda: bool(forwarded))

    assert len(forwarded) == 1
    assert forwarded[0].event_type == "zha_event"
    assert decode_json_dict(forwarded[0].event_data)["command"] == "on"

    await mirror.async_stop()


async def test_unapproved_event_is_dropped(
    channels: tuple[Channel, Channel], hass_runtime: Any
) -> None:
    """Events outside the approved-domain set don't cross the bridge."""
    main, sandbox = channels
    forwarded: list[pb.FireEvent] = []

    async def _on_fire(msg: pb.FireEvent) -> None:
        forwarded.append(msg)

    main.register("sandbox/fire_event", _on_fire)
    main.start()
    sandbox.start()

    approved = ApprovedDomains(["zha"])
    mirror = EventMirror(hass_runtime, approved)
    mirror.register(sandbox)

    # ``hue`` is not in the approved set — drop it.
    hass_runtime.bus.async_fire("hue_event", {"id": 1})
    # ``foo`` has no underscore — never matches.
    hass_runtime.bus.async_fire("foo", {})

    for _ in range(20):
        await asyncio.sleep(0)

    assert forwarded == []

    await mirror.async_stop()


async def test_internal_events_are_skipped(
    channels: tuple[Channel, Channel], hass_runtime: Any
) -> None:
    """``state_changed`` / ``service_registered`` are owned by other mirrors."""
    main, sandbox = channels
    forwarded: list[pb.FireEvent] = []

    async def _on_fire(msg: pb.FireEvent) -> None:
        forwarded.append(msg)

    main.register("sandbox/fire_event", _on_fire)
    main.start()
    sandbox.start()

    # Approve a domain whose name happens to be a prefix of an internal
    # event so the check is meaningful.
    approved = ApprovedDomains(["state", "service"])
    mirror = EventMirror(hass_runtime, approved)
    mirror.register(sandbox)

    hass_runtime.bus.async_fire("state_changed", {"entity_id": "demo.x"})
    hass_runtime.bus.async_fire(
        "service_registered", {"domain": "demo", "service": "do"}
    )

    for _ in range(20):
        await asyncio.sleep(0)

    assert forwarded == []

    await mirror.async_stop()
