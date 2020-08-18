"""Test the Smart Meter Texas sensor entity."""
from homeassistant.components.homeassistant import (
    DOMAIN as HA_DOMAIN,
    SERVICE_UPDATE_ENTITY,
)
from homeassistant.components.smart_meter_texas.const import (
    ELECTRIC_METER,
    ESIID,
    METER_NUMBER,
)
from homeassistant.const import ATTR_ENTITY_ID, CONF_ADDRESS
from homeassistant.setup import async_setup_component

from .conftest import TEST_ENTITY_ID, mock_connection, refresh_data, setup_integration

from tests.async_mock import patch


async def test_sensor(hass, config_entry, aioclient_mock):
    """Test that the sensor is setup."""
    mock_connection(aioclient_mock)
    await setup_integration(hass, config_entry, aioclient_mock)
    await refresh_data(hass, config_entry, aioclient_mock)
    meter = hass.states.get(TEST_ENTITY_ID)

    assert meter
    assert meter.state == "9751.212"


async def test_name(hass, config_entry, aioclient_mock):
    """Test sensor name property."""
    mock_connection(aioclient_mock)
    await setup_integration(hass, config_entry, aioclient_mock)
    await refresh_data(hass, config_entry, aioclient_mock)
    meter = hass.states.get(TEST_ENTITY_ID)

    assert meter.name == f"{ELECTRIC_METER} 123456789"


async def test_attributes(hass, config_entry, aioclient_mock):
    """Test meter attributes."""
    mock_connection(aioclient_mock)
    await setup_integration(hass, config_entry, aioclient_mock)
    await refresh_data(hass, config_entry, aioclient_mock)
    meter = hass.states.get(TEST_ENTITY_ID)

    assert meter.attributes[METER_NUMBER] == "123456789"
    assert meter.attributes[ESIID] == "12345678901234567"
    assert meter.attributes[CONF_ADDRESS] == "123 MAIN ST"


async def test_generic_entity_update_service(hass, config_entry, aioclient_mock):
    """Test generic update entity service homeasasistant/update_entity."""
    mock_connection(aioclient_mock)
    await setup_integration(hass, config_entry, aioclient_mock)
    await async_setup_component(hass, HA_DOMAIN, {})
    with patch("smart_meter_texas.Meter.read_meter") as updater:
        await hass.services.async_call(
            HA_DOMAIN,
            SERVICE_UPDATE_ENTITY,
            {ATTR_ENTITY_ID: TEST_ENTITY_ID},
            blocking=True,
        )
        await hass.async_block_till_done()
        updater.assert_called_once()
