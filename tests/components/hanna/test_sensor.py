"""Tests for the Hanna Instruments sensor platform."""

from typing import Any
from unittest.mock import MagicMock

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry

DEVICE_READINGS = {
    "pool": {"DID": "pool", "messages": {"parameters": [{"name": "ph", "value": 7.2}]}},
    "spa": {"DID": "spa", "messages": {"parameters": [{"name": "ph", "value": 7.8}]}},
}


async def test_sensors_use_own_device_readings(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_hanna_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test each device's sensors show that device's readings."""
    mock_hanna_client.get_devices.return_value = [
        {"DID": "pool", "name": "Pool"},
        {"DID": "spa", "name": "Spa"},
    ]

    def get_last_device_reading(device_id: str) -> dict[str, Any]:
        # The real client keeps only the most recently fetched device's parameters.
        readings = DEVICE_READINGS[device_id]
        mock_hanna_client.parameters = readings["messages"]["parameters"]
        return readings

    mock_hanna_client.get_last_device_reading.side_effect = get_last_device_reading

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    pool_ph = entity_registry.async_get_entity_id(Platform.SENSOR, "hanna", "pool_ph")
    spa_ph = entity_registry.async_get_entity_id(Platform.SENSOR, "hanna", "spa_ph")
    assert pool_ph is not None
    assert spa_ph is not None
    assert hass.states.get(pool_ph).state == "7.2"
    assert hass.states.get(spa_ph).state == "7.8"
