"""Test the No-IP.com Sensor."""
from __future__ import annotations

from unittest.mock import MagicMock

from homeassistant.components.no_ip import sensor
from homeassistant.components.no_ip.const import DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DOMAIN, CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.util.dt import utcnow


async def test_async_setup_entry(hass: HomeAssistant) -> None:
    """Test async_setup_entry function."""
    config_entry = ConfigEntry(1, DOMAIN, "test", {}, "test", {}, utcnow(), None, None)
    coordinator = MagicMock()
    coordinator.data = {
        CONF_DOMAIN: "example.com",
        CONF_IP_ADDRESS: "192.168.0.1",
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
    assert entities[0].native_value == "192.168.0.1"


async def test_noip_sensor_native_value() -> None:
    """Test native_value property of NoIPSensor."""
    coordinator = MagicMock()
    coordinator.data = {
        CONF_DOMAIN: "example.com",
        CONF_IP_ADDRESS: "192.168.0.1",
    }
    entity = sensor.NoIPSensor(coordinator)
    assert entity.native_value == "192.168.0.1"

    coordinator.data = {
        CONF_DOMAIN: "example.com",
    }
    entity = sensor.NoIPSensor(coordinator)
    assert entity.native_value is None
