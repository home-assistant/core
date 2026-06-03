"""Phase 5 tests for :class:`hass_client.entry_runner.EntryRunner`.

Exercises the sandbox-side ``sandbox/entry_setup`` round-trip plus the
``sandbox/call_service`` channel.
"""

import asyncio
import tempfile
from types import ModuleType
from typing import Any

from hass_client._proto import sandbox_pb2 as pb
from hass_client.channel import Channel
from hass_client.codec_protobuf import ProtobufCodec
from hass_client.entry_runner import EntryRunner
from hass_client.flow_runner import FlowRunner
import pytest

from homeassistant import config_entries as ha_config_entries, loader as ha_loader
from homeassistant.config_entries import ConfigEntry, ConfigFlow


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


@pytest.fixture(name="runner")
async def _runner_fixture() -> EntryRunner:
    with tempfile.TemporaryDirectory(prefix="sandbox_entryrunner_") as tmp:
        flow_runner = await FlowRunner.create(config_dir=tmp)
        try:
            yield EntryRunner(flow_runner.hass)
        finally:
            await flow_runner.async_stop()


async def test_entry_setup_calls_integration_setup_entry(
    channels: tuple[Channel, Channel], runner: EntryRunner
) -> None:
    """``sandbox/entry_setup`` runs the integration's async_setup_entry."""
    main, sandbox = channels
    runner.register(sandbox)
    main.start()
    sandbox.start()

    setup_calls: list[ConfigEntry] = []

    async def _async_setup_entry(hass: Any, entry: ConfigEntry) -> bool:
        setup_calls.append(entry)
        return True

    async def _async_unload_entry(_hass: Any, _entry: ConfigEntry) -> bool:
        return True

    class _DemoFlow(ConfigFlow, domain="phase5_demo"):
        VERSION = 1

    # `ConfigFlow.__init_subclass__` adds _DemoFlow to HANDLERS — clean it
    # back up at teardown so other tests don't see a stale handler.
    assert "phase5_demo" in ha_config_entries.HANDLERS

    # Stand up a fake integration in the loader caches. Both the main
    # module and the config_flow module must be present in DATA_COMPONENTS
    # — entry.async_setup imports the latter before calling
    # async_setup_entry.
    module = ModuleType("homeassistant.components.phase5_demo")
    module.DOMAIN = "phase5_demo"
    module.async_setup_entry = _async_setup_entry  # type: ignore[attr-defined]
    module.async_unload_entry = _async_unload_entry  # type: ignore[attr-defined]
    config_flow_module = ModuleType("homeassistant.components.phase5_demo.config_flow")
    runner.hass.data[ha_loader.DATA_COMPONENTS]["phase5_demo"] = module
    runner.hass.data[ha_loader.DATA_COMPONENTS]["phase5_demo.config_flow"] = (
        config_flow_module
    )
    runner.hass.config.components.add("phase5_demo")

    integration = ha_loader.Integration(
        runner.hass,
        "homeassistant.components.phase5_demo",
        None,
        {
            "domain": "phase5_demo",
            "name": "Phase 5 Demo",
            "config_flow": True,
            "documentation": "https://example.com",
            "iot_class": "local_polling",
            "requirements": [],
            "dependencies": [],
            "codeowners": [],
        },
        None,
    )
    runner.hass.data[ha_loader.DATA_INTEGRATIONS] = runner.hass.data.get(
        ha_loader.DATA_INTEGRATIONS, {}
    )
    runner.hass.data[ha_loader.DATA_INTEGRATIONS]["phase5_demo"] = integration

    payload = pb.EntrySetup(
        entry_id="test_entry_id_5",
        domain="phase5_demo",
        title="Demo",
        source="user",
        version=1,
        minor_version=1,
    )
    payload.data.update({"host": "1.2.3.4"})
    result = await main.call("sandbox/entry_setup", payload)

    assert result.ok
    assert not result.HasField("reason")
    assert len(setup_calls) == 1
    assert setup_calls[0].entry_id == "test_entry_id_5"
    assert setup_calls[0].data["host"] == "1.2.3.4"


async def test_entry_setup_reports_failure_reason(
    channels: tuple[Channel, Channel], runner: EntryRunner
) -> None:
    """A failing integration setup surfaces ``ok=False`` with a reason."""
    main, sandbox = channels
    runner.register(sandbox)
    main.start()
    sandbox.start()

    payload = pb.EntrySetup(
        entry_id="missing_entry_id",
        domain="phase5_missing",
        title="Missing",
        source="user",
        version=1,
        minor_version=1,
    )

    result = await main.call("sandbox/entry_setup", payload)
    assert result.ok is False
    assert result.HasField("reason")


async def test_call_service_dispatches_through_services(
    channels: tuple[Channel, Channel], runner: EntryRunner
) -> None:
    """``call_service`` invokes the local service registry."""
    main, sandbox = channels
    runner.register(sandbox)
    main.start()
    sandbox.start()

    seen: list[dict[str, Any]] = []

    async def _svc_handler(call: Any) -> None:
        seen.append(dict(call.data))

    runner.hass.services.async_register("test_call", "do_it", _svc_handler)

    call_msg = pb.CallService(domain="test_call", service="do_it")
    call_msg.service_data.update({"hello": "world"})
    result = await main.call("sandbox/call_service", call_msg)

    # No return_response: proto result has no `response` field set (was
    # `result is None` on the dict wire).
    assert not result.HasField("response")
    assert seen == [{"hello": "world"}]
