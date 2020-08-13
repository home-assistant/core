"""Test Flo by Moen sensor entities."""
from homeassistant.components.flo.const import DOMAIN as FLO_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, CONF_PASSWORD, CONF_USERNAME
from homeassistant.setup import async_setup_component

from .common import TEST_PASSWORD, TEST_USER_ID


async def test_sensors(hass, config_entry, aioclient_mock_fixture):
    """Test Flo by Moen sensors."""
    config_entry.add_to_hass(hass)
    assert await async_setup_component(
        hass, FLO_DOMAIN, {CONF_USERNAME: TEST_USER_ID, CONF_PASSWORD: TEST_PASSWORD}
    )
    await hass.async_block_till_done()

    assert len(hass.data[FLO_DOMAIN][config_entry.entry_id]["devices"]) == 1

    # we should have 5 entities for the device
    assert hass.states.get("sensor.current_system_mode").state == "home"
    assert hass.states.get("sensor.today_s_water_usage").state == "3.7"
    assert hass.states.get("sensor.water_flow_rate").state == "0"
    assert hass.states.get("sensor.water_pressure").state == "54.2"
    assert hass.states.get("sensor.water_temperature").state == "21.1"


async def test_manual_update_entity(
    hass, config_entry, aioclient_mock_fixture, aioclient_mock
):
    """Test manual update entity via service homeasasistant/update_entity."""
    config_entry.add_to_hass(hass)
    assert await async_setup_component(
        hass, FLO_DOMAIN, {CONF_USERNAME: TEST_USER_ID, CONF_PASSWORD: TEST_PASSWORD}
    )
    await hass.async_block_till_done()

    assert len(hass.data[FLO_DOMAIN][config_entry.entry_id]["devices"]) == 1

    await async_setup_component(hass, "homeassistant", {})

    call_count = aioclient_mock.call_count
    await hass.services.async_call(
        "homeassistant",
        "update_entity",
        {ATTR_ENTITY_ID: ["sensor.current_system_mode"]},
        blocking=True,
    )
    assert aioclient_mock.call_count == call_count + 2
