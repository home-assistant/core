"""Tests for :class:`hass_client.entity_bridge.EntityBridge`.

The bridge listens for ``EVENT_STATE_CHANGED`` on the sandbox-private
:class:`HomeAssistant`. We drive it by registering a fake entity into a
:class:`EntityComponent` and firing the matching events; the channel
should see ``sandbox/register_entity`` then ``sandbox/state_changed``.

To stay independent of the entity_registry / device_registry machinery,
we put the entity into the component's ``_entities`` dict manually and
emit synthetic state events.
"""

import asyncio
from datetime import UTC, datetime
import logging
import tempfile
from typing import Any
from unittest.mock import MagicMock

from hass_client._proto import sandbox_pb2 as pb
from hass_client.approved_domains import ApprovedDomains
from hass_client.channel import Channel
from hass_client.codec_protobuf import ProtobufCodec
from hass_client.entity_bridge import EntityBridge
from hass_client.flow_runner import FlowRunner
from hass_client.messages import decode_json_dict
import pytest

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.core import State
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent


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


class _FakeEntity(Entity):
    """Minimal entity exposing the surface ``_describe_entity`` reads."""

    _attr_should_poll = False
    _attr_has_entity_name = False

    def __init__(self) -> None:
        self.entity_id = "demo.lamp"
        self._attr_unique_id = "demo-lamp"
        self._attr_name = "Lamp"
        self._attr_icon = None
        self._attr_supported_features = 0

    @property
    def platform(self) -> Any:
        # ``EntityBridge._entry_id_for`` uses platform.config_entry.entry_id
        # when the entity isn't in the registry. Mock the chain.
        mock = MagicMock()
        mock.config_entry.entry_id = "fake-entry-id"
        mock.domain = "demo"
        return mock

    @property
    def registry_entry(self) -> None:
        return None


@pytest.fixture(name="channels")
async def _channels_fixture() -> tuple[Channel, Channel]:
    main, sandbox = _make_channel_pair()
    yield main, sandbox
    await main.close()
    await sandbox.close()


@pytest.fixture(name="hass_with_demo_component")
async def _hass_with_demo_component_fixture():
    """Yield an HA instance with a ``demo`` EntityComponent ready."""
    with tempfile.TemporaryDirectory(prefix="sandbox_entity_bridge_") as tmp:
        flow_runner = await FlowRunner.create(config_dir=tmp)
        hass = flow_runner.hass
        component: EntityComponent[Entity] = EntityComponent(
            logging.getLogger("test"), "demo", hass
        )
        try:
            yield hass, component
        finally:
            await flow_runner.async_stop()


def test_serialise_device_info_flattens_sets_tuples_and_enums() -> None:
    """The wire form replaces sets/tuples with lists and enums with strings."""
    from hass_client.entity_bridge import _serialise_device_info  # noqa: PLC0415

    from homeassistant.helpers.device_registry import DeviceEntryType  # noqa: PLC0415

    payload = _serialise_device_info(
        {
            "identifiers": {("foo", "1"), ("foo", "2")},
            "connections": {("mac", "00:11:22:33:44:55")},
            "via_device": ("parent_domain", "parent-id"),
            "entry_type": DeviceEntryType.SERVICE,
            "name": "Thermostat",
            "manufacturer": "Acme",
        }
    )

    assert payload is not None
    # set ordering isn't deterministic — compare as sets-of-tuples.
    assert {tuple(item) for item in payload["identifiers"]} == {
        ("foo", "1"),
        ("foo", "2"),
    }
    assert payload["connections"] == [["mac", "00:11:22:33:44:55"]]
    assert payload["via_device"] == ["parent_domain", "parent-id"]
    assert payload["entry_type"] == "service"
    assert payload["name"] == "Thermostat"
    assert payload["manufacturer"] == "Acme"


def test_serialise_device_info_returns_none_for_empty_input() -> None:
    """Empty / missing device_info short-circuits to None."""
    from hass_client.entity_bridge import _serialise_device_info  # noqa: PLC0415

    assert _serialise_device_info(None) is None
    assert _serialise_device_info({}) is None


async def test_bridge_includes_device_info_in_register_payload(
    channels: tuple[Channel, Channel], hass_with_demo_component
) -> None:
    """An entity with ``device_info`` ships it in the register_entity payload."""
    main, sandbox = channels
    hass, component = hass_with_demo_component

    register_calls: list[pb.EntityDescription] = []

    async def _on_register(msg: pb.EntityDescription) -> pb.RegisterEntityResult:
        register_calls.append(msg)
        return pb.RegisterEntityResult(entity_id="demo.with_device_main")

    main.register("sandbox/register_entity", _on_register)
    main.start()
    sandbox.start()

    class _DeviceEntity(_FakeEntity):
        def __init__(self) -> None:
            super().__init__()
            self.entity_id = "demo.with_device"
            self._attr_device_info = {
                "identifiers": {("demo", "dev-1")},
                "name": "Demo Device",
                "manufacturer": "Acme",
            }

    entity = _DeviceEntity()
    component._entities[entity.entity_id] = entity  # noqa: SLF001

    bridge = EntityBridge(hass)
    bridge.register(sandbox)

    now = datetime.now(tz=datetime.now().astimezone().tzinfo)
    hass.bus.async_fire(
        EVENT_STATE_CHANGED,
        {
            "entity_id": entity.entity_id,
            "old_state": None,
            "new_state": State(
                entity.entity_id, "off", {}, last_changed=now, last_updated=now
            ),
        },
    )

    for _ in range(50):
        if register_calls and entity.entity_id in bridge._registered:  # noqa: SLF001
            break
        await asyncio.sleep(0)

    assert len(register_calls) == 1
    device_info = register_calls[0].info.device_info
    assert [(p.key, p.value) for p in device_info.identifiers] == [("demo", "dev-1")]
    assert device_info.name == "Demo Device"
    assert device_info.manufacturer == "Acme"

    await bridge.async_stop()


async def test_bridge_emits_register_and_state_pushes(
    channels: tuple[Channel, Channel], hass_with_demo_component
) -> None:
    """A new entity in the state machine fires register_entity + state_changed."""
    main, sandbox = channels
    hass, component = hass_with_demo_component

    register_calls: list[pb.EntityDescription] = []
    state_calls: list[pb.StateChanged] = []

    async def _on_register(msg: pb.EntityDescription) -> pb.RegisterEntityResult:
        register_calls.append(msg)
        return pb.RegisterEntityResult(entity_id="demo.lamp_main")

    async def _on_state(msg: pb.StateChanged) -> None:
        state_calls.append(msg)

    main.register("sandbox/register_entity", _on_register)
    main.register("sandbox/state_changed", _on_state)
    main.start()
    sandbox.start()

    # Stash a fake entity directly into the EntityComponent so the
    # bridge's `get_entity` lookup finds it.
    entity = _FakeEntity()
    component._entities[entity.entity_id] = entity  # noqa: SLF001

    bridge = EntityBridge(hass)
    bridge.register(sandbox)

    # Simulate the integration calling async_write_ha_state for the first
    # time: state machine fires EVENT_STATE_CHANGED with old_state=None.
    now = datetime.now(tz=datetime.now().astimezone().tzinfo)
    hass.bus.async_fire(
        EVENT_STATE_CHANGED,
        {
            "entity_id": entity.entity_id,
            "old_state": None,
            "new_state": State(
                entity.entity_id, "off", {}, last_changed=now, last_updated=now
            ),
        },
    )

    # Wait until BOTH the channel sees the register call AND the bridge
    # has recorded the entity as registered (the round-trip resolves on a
    # later tick than the handler is invoked).
    for _ in range(50):
        if register_calls and entity.entity_id in bridge._registered:  # noqa: SLF001
            break
        await asyncio.sleep(0)

    assert len(register_calls) == 1
    msg = register_calls[0]
    assert msg.unique_id == "demo-lamp"
    assert msg.domain == "demo"
    assert msg.sandbox_entity_id == "demo.lamp"
    assert msg.entry_id == "fake-entry-id"
    assert msg.initial.state == "off"

    # A subsequent state change becomes a state_changed push.
    new_state = State(entity.entity_id, "on", {"brightness": 200})
    hass.bus.async_fire(
        EVENT_STATE_CHANGED,
        {
            "entity_id": entity.entity_id,
            "old_state": State(entity.entity_id, "off", {}),
            "new_state": new_state,
        },
    )

    for _ in range(50):
        if state_calls:
            break
        await asyncio.sleep(0)

    assert len(state_calls) == 1
    assert state_calls[0].sandbox_entity_id == "demo.lamp"
    assert state_calls[0].state == "on"
    assert decode_json_dict(state_calls[0].attributes)["brightness"] == 200

    await bridge.async_stop()


async def test_state_push_serialises_datetime_attributes(
    channels: tuple[Channel, Channel], hass_with_demo_component
) -> None:
    """Datetime attribute values survive the push path as ISO strings.

    ``encode_json``'s HA-aware encoder coerces the raw datetime inside the
    fire-and-forget push task — the push must arrive with the value
    serialised instead of the task dying.
    """
    main, sandbox = channels
    hass, component = hass_with_demo_component

    state_calls: list[pb.StateChanged] = []

    async def _on_register(msg: pb.EntityDescription) -> pb.RegisterEntityResult:
        return pb.RegisterEntityResult(entity_id="demo.lamp_main")

    async def _on_state(msg: pb.StateChanged) -> None:
        state_calls.append(msg)

    main.register("sandbox/register_entity", _on_register)
    main.register("sandbox/state_changed", _on_state)
    main.start()
    sandbox.start()

    entity = _FakeEntity()
    component._entities[entity.entity_id] = entity  # noqa: SLF001

    bridge = EntityBridge(hass)
    bridge.register(sandbox)
    await _register_initial(bridge, hass, entity)

    detected_at = datetime(2026, 5, 24, 11, 0, tzinfo=UTC)
    hass.bus.async_fire(
        EVENT_STATE_CHANGED,
        {
            "entity_id": entity.entity_id,
            "old_state": State(entity.entity_id, "off", {}),
            "new_state": State(entity.entity_id, "on", {"detected_at": detected_at}),
        },
    )

    for _ in range(50):
        if state_calls:
            break
        await asyncio.sleep(0)

    assert len(state_calls) == 1
    assert state_calls[0].state == "on"
    attributes = decode_json_dict(state_calls[0].attributes)
    assert attributes["detected_at"] == detected_at.isoformat()

    await bridge.async_stop()


async def test_register_attributes_sole_domain_entry_without_linkage(
    channels: tuple[Channel, Channel], hass_with_demo_component
) -> None:
    """An entity with no registry/platform linkage falls back to the domain's entry.

    ``registry_entry`` is None and ``platform.config_entry`` is None (an
    own-domain entity on a bare EntityComponent) — when exactly one loaded
    config entry owns the entity's domain, the registration is attributed
    to it instead of being skipped.
    """
    main, sandbox = channels
    hass, component = hass_with_demo_component

    register_calls: list[pb.EntityDescription] = []

    async def _on_register(msg: pb.EntityDescription) -> pb.RegisterEntityResult:
        register_calls.append(msg)
        return pb.RegisterEntityResult(entity_id="demo.lamp_main")

    main.register("sandbox/register_entity", _on_register)
    main.start()
    sandbox.start()

    config_entry = ConfigEntry(
        version=1,
        minor_version=1,
        domain="demo",
        title="Demo",
        data={},
        options={},
        source="user",
        unique_id=None,
        discovery_keys={},
        subentries_data=(),
    )
    hass.config_entries._entries[config_entry.entry_id] = config_entry  # noqa: SLF001

    class _UnlinkedEntity(_FakeEntity):
        @property
        def platform(self) -> Any:
            # No config-entry linkage anywhere: registry_entry is None
            # (inherited) and the platform carries no config_entry either.
            mock = MagicMock()
            mock.config_entry = None
            mock.domain = "demo"
            return mock

    entity = _UnlinkedEntity()
    component._entities[entity.entity_id] = entity  # noqa: SLF001

    bridge = EntityBridge(hass)
    bridge.register(sandbox)
    await _register_initial(bridge, hass, entity)

    assert len(register_calls) == 1
    assert register_calls[0].entry_id == config_entry.entry_id

    await bridge.async_stop()


async def _register_initial(bridge: EntityBridge, hass: Any, entity: Entity) -> None:
    """Drive the first state-change so ``entity`` is tracked + registered."""
    now = datetime.now(tz=datetime.now().astimezone().tzinfo)
    hass.bus.async_fire(
        EVENT_STATE_CHANGED,
        {
            "entity_id": entity.entity_id,
            "old_state": None,
            "new_state": State(
                entity.entity_id, "off", {}, last_changed=now, last_updated=now
            ),
        },
    )
    for _ in range(50):
        if entity.entity_id in bridge._registered:  # noqa: SLF001
            break
        await asyncio.sleep(0)


async def test_unregister_releases_domain_approval(
    channels: tuple[Channel, Channel], hass_with_demo_component
) -> None:
    """Registering an entity approves its domain; unregistering releases it.

    The per-entity ``approved.add`` in ``_register`` previously had no
    matching decrement, leaking the approval for the process lifetime.
    """
    main, sandbox = channels
    hass, component = hass_with_demo_component

    async def _on_register(msg: pb.EntityDescription) -> pb.RegisterEntityResult:
        return pb.RegisterEntityResult(entity_id="demo.lamp_main")

    async def _on_unregister(msg: pb.UnregisterEntity) -> pb.UnregisterEntityResult:
        return pb.UnregisterEntityResult(ok=True)

    main.register("sandbox/register_entity", _on_register)
    main.register("sandbox/unregister_entity", _on_unregister)
    main.start()
    sandbox.start()

    entity = _FakeEntity()
    component._entities[entity.entity_id] = entity  # noqa: SLF001

    approved = ApprovedDomains()
    bridge = EntityBridge(hass, approved)
    bridge.register(sandbox)

    await _register_initial(bridge, hass, entity)
    assert approved.approves("demo")

    # Entity removed → the only approval for "demo" is released.
    now = datetime.now(tz=datetime.now().astimezone().tzinfo)
    hass.bus.async_fire(
        EVENT_STATE_CHANGED,
        {
            "entity_id": entity.entity_id,
            "old_state": State(entity.entity_id, "off", {}, last_updated=now),
            "new_state": None,
        },
    )
    for _ in range(50):
        if not approved.approves("demo"):
            break
        await asyncio.sleep(0)

    assert not approved.approves("demo")

    await bridge.async_stop()


async def test_state_update_during_register_is_flushed(
    channels: tuple[Channel, Channel], hass_with_demo_component
) -> None:
    """A state change arriving while register is in flight is pushed after.

    The register RPC is held open; a second ``async_set`` lands in the
    entity's pending slot (the single writer is busy awaiting the register, so
    nothing is pushed yet). Once register completes, the writer drains the
    slot and pushes the newer state.
    """
    main, sandbox = channels
    hass, component = hass_with_demo_component

    register_started = asyncio.Event()
    release_register = asyncio.Event()
    register_calls: list[pb.EntityDescription] = []
    state_calls: list[pb.StateChanged] = []

    async def _on_register(msg: pb.EntityDescription) -> pb.RegisterEntityResult:
        register_calls.append(msg)
        register_started.set()
        await release_register.wait()
        return pb.RegisterEntityResult(entity_id="demo.lamp_main")

    async def _on_state(msg: pb.StateChanged) -> None:
        state_calls.append(msg)

    main.register("sandbox/register_entity", _on_register)
    main.register("sandbox/state_changed", _on_state)
    main.start()
    sandbox.start()

    entity = _FakeEntity()
    component._entities[entity.entity_id] = entity  # noqa: SLF001

    bridge = EntityBridge(hass)
    bridge.register(sandbox)

    # First appearance → register, which blocks inside the main handler.
    hass.states.async_set(entity.entity_id, "off", {})
    await asyncio.wait_for(register_started.wait(), timeout=2.0)

    # A fast second update lands in the state machine but is dropped by the
    # bridge because the entity is still pending its register RPC.
    hass.states.async_set(entity.entity_id, "on", {"brightness": 200})
    for _ in range(20):
        await asyncio.sleep(0)
    assert state_calls == []

    # Release register: the bridge re-reads and flushes the coalesced "on".
    release_register.set()
    for _ in range(50):
        if state_calls:
            break
        await asyncio.sleep(0)

    assert len(state_calls) == 1
    assert state_calls[0].state == "on"
    assert decode_json_dict(state_calls[0].attributes)["brightness"] == 200

    await bridge.async_stop()


async def test_state_burst_coalesces_to_single_push(
    channels: tuple[Channel, Channel], hass_with_demo_component
) -> None:
    """A rapid burst of state changes coalesces to one push of the latest.

    The writer task cannot run between the synchronous ``async_set`` calls,
    so each write overwrites the entity's single pending slot; the writer
    then ships one push carrying the final state instead of one per event.
    """
    main, sandbox = channels
    hass, component = hass_with_demo_component

    state_calls: list[pb.StateChanged] = []

    async def _on_register(msg: pb.EntityDescription) -> pb.RegisterEntityResult:
        return pb.RegisterEntityResult(entity_id="demo.lamp_main")

    async def _on_state(msg: pb.StateChanged) -> None:
        state_calls.append(msg)

    main.register("sandbox/register_entity", _on_register)
    main.register("sandbox/state_changed", _on_state)
    main.start()
    sandbox.start()

    entity = _FakeEntity()
    component._entities[entity.entity_id] = entity  # noqa: SLF001

    bridge = EntityBridge(hass)
    bridge.register(sandbox)
    await _register_initial(bridge, hass, entity)

    n_events = 5
    for idx in range(n_events):
        hass.states.async_set(entity.entity_id, f"level_{idx}", {"idx": idx})

    for _ in range(50):
        if state_calls:
            break
        await asyncio.sleep(0)
    # Let everything settle so a non-coalescing bridge would have flushed
    # every push before the count is asserted.
    for _ in range(20):
        await asyncio.sleep(0)

    assert len(state_calls) == 1
    assert state_calls[0].state == f"level_{n_events - 1}"
    assert decode_json_dict(state_calls[0].attributes)["idx"] == n_events - 1

    await bridge.async_stop()


async def test_describe_failure_is_sticky_until_registry_update(
    channels: tuple[Channel, Channel], hass_with_demo_component
) -> None:
    """An undescribable entity is skipped once, not re-attempted per write.

    The first state write for an entity with no live entity object marks it
    skipped; later writes never reach ``_describe`` again. An entity-registry
    update for that entity clears the skip so the next write retries.
    """
    main, sandbox = channels
    hass, component = hass_with_demo_component

    register_calls: list[pb.EntityDescription] = []

    async def _on_register(msg: pb.EntityDescription) -> pb.RegisterEntityResult:
        register_calls.append(msg)
        return pb.RegisterEntityResult(entity_id="demo.lamp_main")

    main.register("sandbox/register_entity", _on_register)
    main.start()
    sandbox.start()

    # No entity in the component: _describe returns None.
    bridge = EntityBridge(hass)
    bridge.register(sandbox)

    hass.states.async_set("demo.lamp", "off", {})
    for _ in range(20):
        await asyncio.sleep(0)
    assert "demo.lamp" in bridge._skipped  # noqa: SLF001

    # Further writes are ignored — no new slot, no describe attempt.
    hass.states.async_set("demo.lamp", "on", {})
    for _ in range(20):
        await asyncio.sleep(0)
    assert register_calls == []

    # The entity becomes describable and its registry entry updates.
    entity = _FakeEntity()
    component._entities[entity.entity_id] = entity  # noqa: SLF001
    hass.bus.async_fire(
        er.EVENT_ENTITY_REGISTRY_UPDATED,
        {"action": "update", "entity_id": entity.entity_id, "changes": {}},
    )
    assert entity.entity_id not in bridge._skipped  # noqa: SLF001

    # A *changed* state (async_set with the previous value fires no
    # EVENT_STATE_CHANGED) now registers the entity.
    hass.states.async_set(entity.entity_id, "dim", {})
    for _ in range(50):
        if register_calls:
            break
        await asyncio.sleep(0)
    assert len(register_calls) == 1

    await bridge.async_stop()


async def test_removal_during_register_unregisters(
    channels: tuple[Channel, Channel], hass_with_demo_component
) -> None:
    """An entity removed while its register RPC is in flight is unregistered.

    The removal lands as a ``_REMOVED`` slot (the writer's in-flight marker
    keeps it from being classified as never-seen); once register completes,
    the writer drains that slot and unregisters — no ghost proxy on main.
    """
    main, sandbox = channels
    hass, component = hass_with_demo_component

    register_started = asyncio.Event()
    release_register = asyncio.Event()
    register_calls: list[pb.EntityDescription] = []
    unregister_calls: list[pb.UnregisterEntity] = []

    async def _on_register(msg: pb.EntityDescription) -> pb.RegisterEntityResult:
        register_calls.append(msg)
        register_started.set()
        await release_register.wait()
        return pb.RegisterEntityResult(entity_id="demo.lamp_main")

    async def _on_unregister(msg: pb.UnregisterEntity) -> pb.UnregisterEntityResult:
        unregister_calls.append(msg)
        return pb.UnregisterEntityResult(ok=True)

    main.register("sandbox/register_entity", _on_register)
    main.register("sandbox/unregister_entity", _on_unregister)
    main.start()
    sandbox.start()

    entity = _FakeEntity()
    component._entities[entity.entity_id] = entity  # noqa: SLF001

    bridge = EntityBridge(hass)
    bridge.register(sandbox)

    hass.states.async_set(entity.entity_id, "off", {})
    await asyncio.wait_for(register_started.wait(), timeout=2.0)

    # Remove the entity while register is still in flight.
    hass.states.async_remove(entity.entity_id)
    for _ in range(20):
        await asyncio.sleep(0)
    assert unregister_calls == []

    # Release register: the bridge sees the pending-removal flag and unregisters.
    release_register.set()
    for _ in range(50):
        if unregister_calls:
            break
        await asyncio.sleep(0)

    assert len(unregister_calls) == 1
    assert unregister_calls[0].sandbox_entity_id == entity.entity_id
    assert entity.entity_id not in bridge._registered  # noqa: SLF001

    await bridge.async_stop()


async def test_entity_registry_update_resends_registration(
    channels: tuple[Channel, Channel], hass_with_demo_component
) -> None:
    """A post-setup name change re-sends register_entity (upsert) once.

    A second identical update is a no-op thanks to the description hash
    guard, so a registry-update storm doesn't flood the channel.
    """
    main, sandbox = channels
    hass, component = hass_with_demo_component

    register_calls: list[pb.EntityDescription] = []

    async def _on_register(msg: pb.EntityDescription) -> pb.RegisterEntityResult:
        register_calls.append(msg)
        return pb.RegisterEntityResult(entity_id="demo.lamp_main")

    main.register("sandbox/register_entity", _on_register)
    main.start()
    sandbox.start()

    entity = _FakeEntity()
    component._entities[entity.entity_id] = entity  # noqa: SLF001

    bridge = EntityBridge(hass)
    bridge.register(sandbox)
    await _register_initial(bridge, hass, entity)
    assert len(register_calls) == 1

    # Integration renames the entity post-setup.
    entity._attr_name = "Renamed Lamp"  # noqa: SLF001
    hass.bus.async_fire(
        er.EVENT_ENTITY_REGISTRY_UPDATED,
        {"action": "update", "entity_id": entity.entity_id, "changes": {}},
    )
    for _ in range(50):
        if len(register_calls) == 2:
            break
        await asyncio.sleep(0)

    assert len(register_calls) == 2
    assert register_calls[1].info.description.name == "Renamed Lamp"
    assert register_calls[1].sandbox_entity_id == "demo.lamp"

    # Let the resend coroutine settle past its await so the description
    # hash is recorded before the next event fires.
    for _ in range(10):
        await asyncio.sleep(0)

    # A second update with nothing changed is suppressed by the hash guard.
    hass.bus.async_fire(
        er.EVENT_ENTITY_REGISTRY_UPDATED,
        {"action": "update", "entity_id": entity.entity_id, "changes": {}},
    )
    for _ in range(20):
        await asyncio.sleep(0)
    assert len(register_calls) == 2

    await bridge.async_stop()


async def test_device_registry_update_resends_linked_entities(
    channels: tuple[Channel, Channel], hass_with_demo_component
) -> None:
    """A device update re-sends register_entity for its tracked entities."""
    main, sandbox = channels
    hass, component = hass_with_demo_component

    register_calls: list[pb.EntityDescription] = []

    async def _on_register(msg: pb.EntityDescription) -> pb.RegisterEntityResult:
        register_calls.append(msg)
        return pb.RegisterEntityResult(entity_id="demo.lamp_main")

    main.register("sandbox/register_entity", _on_register)
    main.start()
    sandbox.start()

    # Link the entity to a device in the registry so the device-update
    # handler can find it via its device_id (FlowRunner.create loads the
    # registries), and register a config entry the device can hang off.
    config_entry = ConfigEntry(
        version=1,
        minor_version=1,
        domain="demo",
        title="Demo",
        data={},
        options={},
        source="user",
        unique_id=None,
        discovery_keys={},
        subentries_data=(),
    )
    hass.config_entries._entries[config_entry.entry_id] = config_entry  # noqa: SLF001
    device_reg = dr.async_get(hass)
    device = device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("demo", "dev-1")},
        name="Demo Device",
        sw_version="1.0",
    )
    ent_reg = er.async_get(hass)
    registry_entry = ent_reg.async_get_or_create(
        "demo", "demo", "demo-lamp", suggested_object_id="lamp", device_id=device.id
    )

    class _DeviceEntity(_FakeEntity):
        def __init__(self) -> None:
            super().__init__()
            self.entity_id = registry_entry.entity_id
            self._attr_device_info = {
                "identifiers": {("demo", "dev-1")},
                "name": "Demo Device",
                "sw_version": "1.0",
            }

    entity = _DeviceEntity()
    component._entities[entity.entity_id] = entity  # noqa: SLF001

    bridge = EntityBridge(hass)
    bridge.register(sandbox)
    await _register_initial(bridge, hass, entity)
    assert len(register_calls) == 1
    assert register_calls[0].info.device_info.sw_version == "1.0"

    # Firmware bump: the entity now reports a new sw_version and the device
    # registry fires its updated event.
    entity._attr_device_info["sw_version"] = "2.0"  # noqa: SLF001
    hass.bus.async_fire(
        dr.EVENT_DEVICE_REGISTRY_UPDATED,
        {"action": "update", "device_id": device.id, "changes": {}},
    )
    for _ in range(50):
        if len(register_calls) == 2:
            break
        await asyncio.sleep(0)

    assert len(register_calls) == 2
    assert register_calls[1].info.device_info.sw_version == "2.0"

    await bridge.async_stop()
