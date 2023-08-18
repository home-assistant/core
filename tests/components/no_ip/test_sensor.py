"""Test the No-IP.com Sensor."""
from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock

from homeassistant.components.no_ip import sensor
from homeassistant.components.no_ip.const import DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DOMAIN, CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.util.dt import utcnow


def get_test_config_dir(*add_path):
    """Return a path to a test config dir."""
    return os.path.join(os.path.dirname(__file__), "testing_config", *add_path)


async def test_async_added_to_hass() -> None:
    """Test async_added_to_hass method of NoIPSensor."""
    coordinator = MagicMock()
    coordinator.data = {
        CONF_DOMAIN: "example.com",
        CONF_IP_ADDRESS: "1.2.3.4",
    }
    hass = HomeAssistant(get_test_config_dir())
    entity = sensor.NoIPSensor(coordinator)
    entity.hass = hass

    # Mock the async_get_last_sensor_data method to return None
    async_get_last_sensor_data_mock = AsyncMock(return_value=None)
    entity.async_get_last_sensor_data = async_get_last_sensor_data_mock

    # Call async_added_to_hass method
    await entity.async_added_to_hass()

    # Assert that native_value is set correctly
    assert entity.native_value == "1.2.3.4"
    assert entity.name == "example.com"
    assert entity.unique_id == "example.com"

    # Simulate a state change and ensure that native_value is updated
    coordinator.data[CONF_IP_ADDRESS] = "4.3.2.1"
    async_dispatcher_send(hass, f"{DOMAIN}_{entity.unique_id}")
    await hass.async_block_till_done()
    assert entity.native_value == "4.3.2.1"


async def test_async_setup_entry(hass: HomeAssistant) -> None:
    """Test async_setup_entry function."""
    config_entry = ConfigEntry(1, DOMAIN, "test", {}, "test", {}, utcnow(), None, None)
    coordinator = MagicMock()
    coordinator.data = {
        CONF_DOMAIN: "example.com",
        CONF_IP_ADDRESS: "1.2.3.4",
    }
    hass.data[DOMAIN] = {config_entry.entry_id: coordinator}
    async_add_entities = MagicMock()

    await sensor.async_setup_entry(hass, config_entry, async_add_entities)

    async_add_entities.assert_called_once()
    args, kwargs = async_add_entities.call_args
    entities = args[0]
    assert len(entities) == 1
    assert isinstance(entities[0], sensor.NoIPSensor)
    assert entities[0].name == "example.com"
    assert entities[0].unique_id == "example.com"
    assert entities[0].native_value == "1.2.3.4"


async def test_noip_sensor_native_value() -> None:
    """Test native_value property of NoIPSensor."""
    coordinator = MagicMock()
    coordinator.data = {
        CONF_DOMAIN: "example.com",
        CONF_IP_ADDRESS: "1.2.3.4",
    }
    entity = sensor.NoIPSensor(coordinator)
    assert entity.native_value == "1.2.3.4"

    coordinator.data = {
        CONF_DOMAIN: "example.com",
    }
    entity = sensor.NoIPSensor(coordinator)
    assert entity.native_value is None
