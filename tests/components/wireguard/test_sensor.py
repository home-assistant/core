"""Test the WireGuard sensor platform."""
from unittest.mock import patch

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.components.wireguard.const import DEFAULT_HOST, DOMAIN
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_HOST,
    UnitOfInformation,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er

from .conftest import mocked_requests

from tests.common import MockConfigEntry


async def test_entity_registry(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Tests that the devices are registered in the entity registry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="UNIQUE_TEST_ID",
        data={CONF_HOST: DEFAULT_HOST},
    )
    config_entry.add_to_hass(hass)

    with patch("requests.get", side_effect=mocked_requests):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        coordinator = hass.data[DOMAIN][config_entry.entry_id]
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    entry1: er.RegistryEntry = entity_registry.async_get(
        "sensor.dummy_latest_handshake"
    )
    assert entry1.unique_id == "Dummy_latest_handshake"
    assert entry1.original_name == "Latest Handshake"

    state1: State = hass.states.get("sensor.dummy_latest_handshake")
    assert state1
    assert state1.state == "unknown"
    assert state1.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.TIMESTAMP

    entry2: er.RegistryEntry = entity_registry.async_get("sensor.dummy_received")
    assert entry2.unique_id == "Dummy_transfer_rx"
    assert entry2.original_name == "Received"

    state2: State = hass.states.get("sensor.dummy_received")
    assert state2
    assert state2.state == "0.0"
    assert state2.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.DATA_SIZE
    assert state2.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfInformation.MEGABYTES

    entry3: er.RegistryEntry = entity_registry.async_get("sensor.dummy_sent")
    assert entry3.unique_id == "Dummy_transfer_tx"
    assert entry3.original_name == "Sent"

    state3: State = hass.states.get("sensor.dummy_sent")
    assert state3
    assert state3.state == "0.0"
    assert state3.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.DATA_SIZE
    assert state3.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfInformation.MEGABYTES
