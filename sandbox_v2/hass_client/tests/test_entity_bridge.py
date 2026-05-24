"""Phase 5 tests for :class:`hass_client.entity_bridge.EntityBridge`.

The bridge listens for ``EVENT_STATE_CHANGED`` on the sandbox-private
:class:`HomeAssistant`. We drive it by registering a fake entity into a
:class:`EntityComponent` and firing the matching events; the channel
should see ``sandbox_v2/register_entity`` then ``sandbox_v2/state_changed``.

To stay independent of the entity_registry / device_registry machinery,
we put the entity into the component's ``_entities`` dict manually and
emit synthetic state events.
"""

import asyncio
from datetime import datetime
import logging
import tempfile
from typing import Any
from unittest.mock import MagicMock

from hass_client.channel import Channel
from hass_client.entity_bridge import EntityBridge
from hass_client.flow_runner import FlowRunner
import pytest

from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.core import State
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
        Channel(reader_a, _LoopbackWriter(reader_b), name="main"),  # type: ignore[arg-type]
        Channel(reader_b, _LoopbackWriter(reader_a), name="sandbox"),  # type: ignore[arg-type]
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
    with tempfile.TemporaryDirectory(prefix="sandbox_v2_entity_bridge_") as tmp:
        flow_runner = await FlowRunner.create(config_dir=tmp)
        hass = flow_runner.hass
        component: EntityComponent[Entity] = EntityComponent(
            logging.getLogger("test"), "demo", hass
        )
        try:
            yield hass, component
        finally:
            await flow_runner.async_stop()


async def test_bridge_emits_register_and_state_pushes(
    channels: tuple[Channel, Channel], hass_with_demo_component
) -> None:
    """A new entity in the state machine fires register_entity + state_changed."""
    main, sandbox = channels
    hass, component = hass_with_demo_component

    register_calls: list[dict[str, Any]] = []
    state_calls: list[dict[str, Any]] = []

    async def _on_register(payload: dict[str, Any]) -> dict[str, str]:
        register_calls.append(payload)
        return {"entity_id": "demo.lamp_main"}

    async def _on_state(payload: dict[str, Any]) -> None:
        state_calls.append(payload)

    main.register("sandbox_v2/register_entity", _on_register)
    main.register("sandbox_v2/state_changed", _on_state)
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
    payload = register_calls[0]
    assert payload["unique_id"] == "demo-lamp"
    assert payload["domain"] == "demo"
    assert payload["sandbox_entity_id"] == "demo.lamp"
    assert payload["entry_id"] == "fake-entry-id"
    assert payload["initial_state"] == "off"

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
    assert state_calls[0]["sandbox_entity_id"] == "demo.lamp"
    assert state_calls[0]["new_state"]["state"] == "on"
    assert state_calls[0]["new_state"]["attributes"]["brightness"] == 200

    await bridge.async_stop()
