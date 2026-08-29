"""Test function in __init__.py."""

from collections.abc import Callable
from unittest.mock import MagicMock

from mysensors import BaseSyncGateway
from mysensors.sensor import Sensor

from homeassistant.components.mysensors import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.typing import WebSocketGenerator


async def test_load_unload(
    hass: HomeAssistant,
    door_sensor: Sensor,
    transport: MagicMock,
    integration: MockConfigEntry,
    receive_message: Callable[[str], None],
) -> None:
    """Test loading and unloading the MySensors config entry."""
    config_entry = integration

    assert config_entry.state is ConfigEntryState.LOADED

    entity_id = "binary_sensor.door_sensor_1_1"
    state = hass.states.get(entity_id)

    assert state
    assert state.state != STATE_UNAVAILABLE

    receive_message("1;1;1;0;16;1\n")
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)

    assert state
    assert state.state != STATE_UNAVAILABLE

    assert await hass.config_entries.async_unload(config_entry.entry_id)

    assert transport.return_value.disconnect.call_count == 1

    state = hass.states.get(entity_id)

    assert state
    assert state.state == STATE_UNAVAILABLE

    receive_message("1;1;1;0;16;1\n")
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)

    assert state
    assert state.state == STATE_UNAVAILABLE


async def test_remove_config_entry_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    gps_sensor: Sensor,
    integration: MockConfigEntry,
    gateway: BaseSyncGateway,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test that a device can be removed ok."""
    entity_id = "sensor.gps_sensor_1_1"
    node_id = 1
    config_entry = integration
    assert await async_setup_component(hass, "config", {})
    await hass.async_block_till_done()

    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{config_entry.entry_id}-{node_id}"), config_entry.entry_id
    )
    state = hass.states.get(entity_id)

    assert gateway.sensors
    assert gateway.sensors[node_id]
    assert device_entry
    assert state

    client = await hass_ws_client(hass)
    response = await client.remove_device(device_entry.id)
    assert response["success"]
    await hass.async_block_till_done()

    assert node_id not in gateway.sensors
    assert gateway.tasks.persistence.need_save is True
    assert not device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{config_entry.entry_id}-1"), config_entry.entry_id
    )
    assert not entity_registry.async_get(entity_id)
    assert not hass.states.get(entity_id)


async def test_remove_config_entry_device_rejects_child_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    integration: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test that removing an unexpected child device is rejected."""
    config_entry = integration
    assert await async_setup_component(hass, "config", {})

    parent_device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "test_parent_device")},
    )
    child_device = device_registry.async_get_or_create_child(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "test_child_device")},
        parent_device_id=parent_device.id,
    )

    client = await hass_ws_client(hass)
    response = await client.remove_device(child_device.id)
    assert not response["success"]
    assert (
        response["error"]["message"]
        == "Failed to remove device entry, rejected by integration"
    )
    assert device_registry.async_get(child_device.id)
