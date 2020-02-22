"""Tests for the pvpc_hourly_pricing component."""
from homeassistant.components.pvpc_hourly_pricing import ATTR_TARIFF, DOMAIN
from homeassistant.const import CONF_NAME
from homeassistant.setup import async_setup_component

from . import check_valid_state


async def test_basic_setup(hass):
    """Test component setup creates entry from config and first state is valid."""
    config = {DOMAIN: [{CONF_NAME: "test", ATTR_TARIFF: "discriminacion"}]}
    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()
    state = hass.states.get("sensor.test")
    check_valid_state(state, tariff="discriminacion")


async def test_basic_setup_as_sensor_platform(hass):
    """Test component setup creates entry from config as a sensor platform."""
    config_platform = {
        "sensor": {"platform": DOMAIN, CONF_NAME: "test", ATTR_TARIFF: "normal"}
    }
    assert await async_setup_component(hass, "sensor", config_platform)
    await hass.async_block_till_done()
    state = hass.states.get("sensor.test")
    check_valid_state(state, tariff="normal")
