"""Test the WireGuard sensor platform."""
from unittest.mock import MagicMock

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.components.wireguard.const import DOMAIN
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    UnitOfInformation,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


async def test_entity_registry(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    config_entry: MockConfigEntry,
    coordinator_client: MagicMock,
) -> None:
    """Tests that the devices are registered in the entity registry."""
    config_entry.add_to_hass(hass)
    coordinator_client.side_effect = None

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert coordinator.last_update_success

    entry1: er.RegistryEntry = entity_registry.async_get(
        "sensor.empty_latest_handshake"
    )
    assert entry1.unique_id == "EMPTY_latest_handshake"
    assert entry1.original_name == "Latest Handshake"

    state1: State = hass.states.get("sensor.empty_latest_handshake")
    assert state1
    assert state1.state == "unknown"
    assert state1.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.TIMESTAMP

    entry2: er.RegistryEntry = entity_registry.async_get("sensor.empty_received")
    assert entry2.unique_id == "EMPTY_transfer_rx"
    assert entry2.original_name == "Received"

    state2: State = hass.states.get("sensor.empty_received")
    assert state2
    assert state2.state == "0.0"
    assert state2.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.DATA_SIZE
    assert state2.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfInformation.MEGABYTES

    entry3: er.RegistryEntry = entity_registry.async_get("sensor.empty_sent")
    assert entry3.unique_id == "EMPTY_transfer_tx"
    assert entry3.original_name == "Sent"

    state3: State = hass.states.get("sensor.empty_sent")
    assert state3
    assert state3.state == "0.0"
    assert state3.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.DATA_SIZE
    assert state3.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfInformation.MEGABYTES
