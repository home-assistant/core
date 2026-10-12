"""Tests for the Hanna Instruments sensor platform."""

from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from requests.exceptions import RequestException

from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, async_fire_time_changed

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


@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(RequestException("Connection failed"), id="request_error"),
        pytest.param(KeyError("parameters"), id="key_error"),
        pytest.param(IndexError("list index out of range"), id="index_error"),
    ],
)
async def test_sensor_unavailable_on_update_error(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    mock_hanna_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
) -> None:
    """Test sensors become unavailable on update errors and recover afterwards."""
    mock_hanna_client.get_devices.return_value = [{"DID": "pool", "name": "Pool"}]
    mock_hanna_client.get_last_device_reading.return_value = DEVICE_READINGS["pool"]

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    pool_ph = entity_registry.async_get_entity_id(Platform.SENSOR, "hanna", "pool_ph")
    assert pool_ph is not None
    assert hass.states.get(pool_ph).state == "7.2"

    mock_hanna_client.get_last_device_reading.side_effect = exception
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(pool_ph).state == STATE_UNAVAILABLE

    mock_hanna_client.get_last_device_reading.side_effect = None
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(pool_ph).state == "7.2"
