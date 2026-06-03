"""Phase 6 tests for :class:`hass_client.service_mirror.ServiceMirror`.

Drives the mirror against a real sandbox-private :class:`HomeAssistant`
(via :class:`hass_client.flow_runner.FlowRunner`) and an in-memory
channel pair. The mirror reacts to ``EVENT_SERVICE_REGISTERED`` so we
register services through ``hass.services.async_register`` and check
what lands on the main side.
"""

import asyncio
import tempfile
from typing import Any

from hass_client._proto import sandbox_v2_pb2 as pb
from hass_client.approved_domains import ApprovedDomains
from hass_client.channel import Channel
from hass_client.codec_protobuf import ProtobufCodec
from hass_client.flow_runner import FlowRunner
from hass_client.service_mirror import ServiceMirror
import pytest

from homeassistant.core import SupportsResponse


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
    with tempfile.TemporaryDirectory(prefix="sandbox_v2_service_mirror_") as tmp:
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


async def test_register_service_pushes_to_main(
    channels: tuple[Channel, Channel], hass_runtime: Any
) -> None:
    """An approved-domain service registration becomes one push to main."""
    main, sandbox = channels
    register_calls: list[pb.RegisterService] = []

    async def _on_register(msg: pb.RegisterService) -> pb.RegisterServiceResult:
        register_calls.append(msg)
        return pb.RegisterServiceResult(ok=True, installed=True)

    main.register("sandbox_v2/register_service", _on_register)
    main.start()
    sandbox.start()

    approved = ApprovedDomains(["phase6_demo"])
    mirror = ServiceMirror(hass_runtime, approved)
    mirror.register(sandbox)

    async def _svc(_call: Any) -> None:
        return None

    hass_runtime.services.async_register(
        "phase6_demo",
        "do_thing",
        _svc,
        supports_response=SupportsResponse.NONE,
    )

    await _wait_until(lambda: bool(register_calls))

    assert len(register_calls) == 1
    assert register_calls[0].domain == "phase6_demo"
    assert register_calls[0].service == "do_thing"
    assert register_calls[0].supports_response == "none"

    await mirror.async_stop()


async def test_unapproved_domain_is_rejected(
    channels: tuple[Channel, Channel], hass_runtime: Any
) -> None:
    """A service for an un-approved domain never reaches main."""
    main, sandbox = channels
    register_calls: list[pb.RegisterService] = []

    async def _on_register(msg: pb.RegisterService) -> pb.RegisterServiceResult:
        register_calls.append(msg)
        return pb.RegisterServiceResult(ok=True, installed=True)

    main.register("sandbox_v2/register_service", _on_register)
    main.start()
    sandbox.start()

    approved = ApprovedDomains(["phase6_demo"])
    mirror = ServiceMirror(hass_runtime, approved)
    mirror.register(sandbox)

    async def _svc(_call: Any) -> None:
        return None

    hass_runtime.services.async_register(
        "evil_domain",
        "exfiltrate",
        _svc,
    )

    # Give the mirror a few ticks to (incorrectly) push anything.
    for _ in range(20):
        await asyncio.sleep(0)

    assert register_calls == []

    await mirror.async_stop()


async def test_unregister_service_propagates(
    channels: tuple[Channel, Channel], hass_runtime: Any
) -> None:
    """Removing a mirrored service pushes ``unregister_service`` to main."""
    main, sandbox = channels
    register_calls: list[pb.RegisterService] = []
    unregister_calls: list[pb.UnregisterService] = []

    async def _on_register(msg: pb.RegisterService) -> pb.RegisterServiceResult:
        register_calls.append(msg)
        return pb.RegisterServiceResult(ok=True, installed=True)

    async def _on_unregister(
        msg: pb.UnregisterService,
    ) -> pb.UnregisterServiceResult:
        unregister_calls.append(msg)
        return pb.UnregisterServiceResult(ok=True, removed=True)

    main.register("sandbox_v2/register_service", _on_register)
    main.register("sandbox_v2/unregister_service", _on_unregister)
    main.start()
    sandbox.start()

    approved = ApprovedDomains(["phase6_demo"])
    mirror = ServiceMirror(hass_runtime, approved)
    mirror.register(sandbox)

    async def _svc(_call: Any) -> None:
        return None

    hass_runtime.services.async_register("phase6_demo", "go", _svc)
    await _wait_until(lambda: bool(register_calls))

    hass_runtime.services.async_remove("phase6_demo", "go")
    await _wait_until(lambda: bool(unregister_calls))

    assert len(unregister_calls) == 1
    assert unregister_calls[0].domain == "phase6_demo"
    assert unregister_calls[0].service == "go"

    await mirror.async_stop()
