"""Tests for :class:`hass_client.entry_runner.EntryRunner`.

Exercises the sandbox-side ``sandbox/entry_setup`` round-trip plus the
``sandbox/call_service`` channel.
"""

import asyncio
import tempfile
from types import ModuleType
from typing import Any

from hass_client._proto import sandbox_pb2 as pb
from hass_client.channel import Channel, ChannelRemoteError
from hass_client.codec_protobuf import ProtobufCodec
from hass_client.entry_runner import EntryRunner
from hass_client.flow_runner import FlowRunner
from hass_client.messages import decode_json_dict, encode_json
import pytest

from homeassistant import config_entries as ha_config_entries, loader as ha_loader
from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_component import DATA_INSTANCES


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

    class _DemoFlow(ConfigFlow, domain="demo_setup"):
        VERSION = 1

    # `ConfigFlow.__init_subclass__` adds _DemoFlow to HANDLERS — clean it
    # back up at teardown so other tests don't see a stale handler.
    assert "demo_setup" in ha_config_entries.HANDLERS

    # Stand up a fake integration in the loader caches. Both the main
    # module and the config_flow module must be present in DATA_COMPONENTS
    # — entry.async_setup imports the latter before calling
    # async_setup_entry.
    module = ModuleType("homeassistant.components.demo_setup")
    module.DOMAIN = "demo_setup"
    module.async_setup_entry = _async_setup_entry  # type: ignore[attr-defined]
    module.async_unload_entry = _async_unload_entry  # type: ignore[attr-defined]
    config_flow_module = ModuleType("homeassistant.components.demo_setup.config_flow")
    runner.hass.data[ha_loader.DATA_COMPONENTS]["demo_setup"] = module
    runner.hass.data[ha_loader.DATA_COMPONENTS]["demo_setup.config_flow"] = (
        config_flow_module
    )
    runner.hass.config.components.add("demo_setup")

    integration = ha_loader.Integration(
        runner.hass,
        "homeassistant.components.demo_setup",
        None,
        {
            "domain": "demo_setup",
            "name": "Demo Setup",
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
    runner.hass.data[ha_loader.DATA_INTEGRATIONS]["demo_setup"] = integration

    payload = pb.EntrySetup(
        entry_id="test_entry_id_5",
        domain="demo_setup",
        title="Demo",
        source="user",
        version=1,
        minor_version=1,
    )
    payload.data = encode_json({"host": "1.2.3.4", "port": 8123})
    result = await main.call("sandbox/entry_setup", payload)

    assert result.ok
    assert not result.HasField("reason")
    assert len(setup_calls) == 1
    assert setup_calls[0].entry_id == "test_entry_id_5"
    assert setup_calls[0].data["host"] == "1.2.3.4"
    # Int config survives the JSON wire as int, not float.
    assert setup_calls[0].data["port"] == 8123
    assert isinstance(setup_calls[0].data["port"], int)


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
        domain="demo_missing",
        title="Missing",
        source="user",
        version=1,
        minor_version=1,
    )

    result = await main.call("sandbox/entry_setup", payload)
    assert result.ok is False
    assert result.HasField("reason")


async def test_failed_entry_setup_is_retryable(
    channels: tuple[Channel, Channel], runner: EntryRunner
) -> None:
    """A failed setup frees the entry_id so main can re-send entry_setup.

    The first attempt fails; the entry must not linger in the sandbox's
    config_entries (else the retry is rejected with "entry already loaded").
    The second attempt for the same entry_id then succeeds.
    """
    main, sandbox = channels
    runner.register(sandbox)
    main.start()
    sandbox.start()

    attempts: list[str] = []

    async def _async_setup_entry(hass: Any, entry: ConfigEntry) -> bool:
        attempts.append(entry.entry_id)
        # Fail the first attempt, succeed the second.
        return len(attempts) >= 2

    async def _async_unload_entry(_hass: Any, _entry: ConfigEntry) -> bool:
        return True

    class _DemoFlow(ConfigFlow, domain="demo_retry"):
        VERSION = 1

    assert "demo_retry" in ha_config_entries.HANDLERS

    module = ModuleType("homeassistant.components.demo_retry")
    module.DOMAIN = "demo_retry"
    module.async_setup_entry = _async_setup_entry  # type: ignore[attr-defined]
    module.async_unload_entry = _async_unload_entry  # type: ignore[attr-defined]
    config_flow_module = ModuleType("homeassistant.components.demo_retry.config_flow")
    runner.hass.data[ha_loader.DATA_COMPONENTS]["demo_retry"] = module
    runner.hass.data[ha_loader.DATA_COMPONENTS]["demo_retry.config_flow"] = (
        config_flow_module
    )

    integration = ha_loader.Integration(
        runner.hass,
        "homeassistant.components.demo_retry",
        None,
        {
            "domain": "demo_retry",
            "name": "Demo Retry",
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
    runner.hass.data[ha_loader.DATA_INTEGRATIONS]["demo_retry"] = integration

    payload = pb.EntrySetup(
        entry_id="retry_entry_id",
        domain="demo_retry",
        title="Demo Retry",
        source="user",
        version=1,
        minor_version=1,
    )

    # First attempt fails → ok=False and the entry is dropped.
    result1 = await main.call("sandbox/entry_setup", payload)
    assert result1.ok is False
    assert runner.hass.config_entries.async_get_entry("retry_entry_id") is None

    # Retry with the same entry_id succeeds — no "entry already loaded".
    result2 = await main.call("sandbox/entry_setup", payload)
    assert result2.ok is True
    assert not result2.HasField("reason")
    assert attempts == ["retry_entry_id", "retry_entry_id"]


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
    call_msg.service_data = encode_json({"hello": "world", "brightness": 255})
    result = await main.call("sandbox/call_service", call_msg)

    # No return_response: proto result has no `response` field set (was
    # `result is None` on the dict wire).
    assert not result.HasField("response")
    assert seen == [{"hello": "world", "brightness": 255}]
    # Int service-data field arrives as int on the sandbox side.
    assert isinstance(seen[0]["brightness"], int)


class _FakeEntity:
    """Minimal stand-in entity exercising the EntityQuery handler."""

    async def async_release_notes(self) -> str:
        return "## notes"

    async def echo(self, **kwargs: Any) -> dict[str, Any]:
        return kwargs

    async def boom(self) -> None:
        raise ServiceValidationError("bad input")


class _FakeComponent:
    """Stand-in EntityComponent that resolves entities by id."""

    def __init__(self, entities: dict[str, Any]) -> None:
        self._entities = entities

    def get_entity(self, entity_id: str) -> Any:
        return self._entities.get(entity_id)


def _install_fake_entity(runner: EntryRunner, entity_id: str) -> None:
    domain = entity_id.split(".", 1)[0]
    instances = runner.hass.data.setdefault(DATA_INSTANCES, {})
    instances[domain] = _FakeComponent({entity_id: _FakeEntity()})


async def test_entity_query_invokes_method(
    channels: tuple[Channel, Channel], runner: EntryRunner
) -> None:
    """``entity_query`` resolves the entity, runs the method, wraps the value."""
    main, sandbox = channels
    runner.register(sandbox)
    main.start()
    sandbox.start()
    _install_fake_entity(runner, "update.demo")

    msg = pb.EntityQuery(sandbox_entity_id="update.demo", method="async_release_notes")
    result = await main.call("sandbox/entity_query", msg)
    assert decode_json_dict(result.result) == {"value": "## notes"}


async def test_entity_query_passes_kwargs(
    channels: tuple[Channel, Channel], runner: EntryRunner
) -> None:
    """``entity_query`` forwards the decoded args as kwargs."""
    main, sandbox = channels
    runner.register(sandbox)
    main.start()
    sandbox.start()
    _install_fake_entity(runner, "update.demo")

    msg = pb.EntityQuery(sandbox_entity_id="update.demo", method="echo")
    msg.args = encode_json({"a": "x", "b": "y"})
    result = await main.call("sandbox/entity_query", msg)
    assert decode_json_dict(result.result) == {"value": {"a": "x", "b": "y"}}


async def test_entity_query_unknown_entity(
    channels: tuple[Channel, Channel], runner: EntryRunner
) -> None:
    """An unknown entity_id surfaces as a channel error."""
    main, sandbox = channels
    runner.register(sandbox)
    main.start()
    sandbox.start()

    msg = pb.EntityQuery(
        sandbox_entity_id="update.missing", method="async_release_notes"
    )
    with pytest.raises(ChannelRemoteError):
        await main.call("sandbox/entity_query", msg)


async def test_entity_query_unknown_method(
    channels: tuple[Channel, Channel], runner: EntryRunner
) -> None:
    """An unknown method surfaces as a channel error."""
    main, sandbox = channels
    runner.register(sandbox)
    main.start()
    sandbox.start()
    _install_fake_entity(runner, "update.demo")

    msg = pb.EntityQuery(sandbox_entity_id="update.demo", method="does_not_exist")
    with pytest.raises(ChannelRemoteError):
        await main.call("sandbox/entity_query", msg)


async def test_entity_query_method_raises(
    channels: tuple[Channel, Channel], runner: EntryRunner
) -> None:
    """A method that raises propagates the exception type on the error frame."""
    main, sandbox = channels
    runner.register(sandbox)
    main.start()
    sandbox.start()
    _install_fake_entity(runner, "update.demo")

    msg = pb.EntityQuery(sandbox_entity_id="update.demo", method="boom")
    with pytest.raises(ChannelRemoteError) as err:
        await main.call("sandbox/entity_query", msg)
    assert err.value.error_type == "ServiceValidationError"


async def test_entry_setup_real_platform_adds_entities(
    channels: tuple[Channel, Channel], runner: EntryRunner
) -> None:
    """A real integration's entity platform adds entities on the private hass.

    Regression test for the missing registry loads: an unloaded
    ``EntityRegistry`` has no ``.entities``, so every
    ``EntityPlatform._async_add_entity`` died with ``AttributeError`` while
    ``entry_setup`` still reported ok — the sandbox bridged zero entities.
    Driving the real ``sun`` integration end-to-end pins the whole path.
    """
    main, sandbox = channels
    runner.register(sandbox)
    main.start()
    sandbox.start()

    payload = pb.EntrySetup(
        entry_id="sun_entry",
        domain="sun",
        title="Sun",
        source="user",
        version=1,
        minor_version=1,
    )
    result = await main.call("sandbox/entry_setup", payload)
    assert result.ok, result.reason

    hass = runner.hass
    await hass.async_block_till_done()
    assert hass.states.get("sun.sun") is not None
    ent_reg = er.async_get(hass)
    assert ent_reg.async_get_entity_id("sensor", "sun", "sun_entry-next_dawn")
