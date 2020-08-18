"""Test the Smart Meter Texas sensor entity."""
from homeassistant.components.smart_meter_texas.const import (
    ELECTRIC_METER,
    ESIID,
    METER_NUMBER,
)
from homeassistant.const import CONF_ADDRESS

from .conftest import mock_connection, refresh_data, setup_integration


async def test_sensor(hass, config_entry, aioclient_mock):
    """Test that the sensor is setup."""
    mock_connection(aioclient_mock)
    await setup_integration(hass, config_entry, aioclient_mock)
    await refresh_data(hass, config_entry, aioclient_mock)
    meter = hass.states.get("sensor.electric_meter_123456789")

    assert meter
    assert meter.state == "9751.212"


async def test_name(hass, config_entry, aioclient_mock):
    """Test sensor name property."""
    mock_connection(aioclient_mock)
    await setup_integration(hass, config_entry, aioclient_mock)
    await refresh_data(hass, config_entry, aioclient_mock)
    meter = hass.states.get("sensor.electric_meter_123456789")

    assert meter.name == f"{ELECTRIC_METER} 123456789"


async def test_attributes(hass, config_entry, aioclient_mock):
    """Test meter attributes."""
    mock_connection(aioclient_mock)
    await setup_integration(hass, config_entry, aioclient_mock)
    await refresh_data(hass, config_entry, aioclient_mock)
    meter = hass.states.get("sensor.electric_meter_123456789")

    assert meter.attributes[METER_NUMBER] == "123456789"
    assert meter.attributes[ESIID] == "12345678901234567"
    assert meter.attributes[CONF_ADDRESS] == "123 MAIN ST"
