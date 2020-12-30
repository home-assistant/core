"""Tests for Generic Water heater."""
import pytest

from homeassistant.components import switch
from homeassistant.components.generic_water_heater import (
    CONF_HEATER,
    CONF_SENSOR,
    CONF_TARGET_TEMP,
    CONF_TEMP_DELTA,
    DOMAIN,
)
from homeassistant.const import ATTR_TEMPERATURE, STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import CoreState, State
from homeassistant.setup import async_setup_component
from homeassistant.util.unit_system import METRIC_SYSTEM

from tests.common import mock_restore_cache
from tests.components.water_heater import common

WATER_HEATER = "water_heater.my_water_heater"
SWITCH_HEATER = "switch.ac_2"
SENSOR_TEMPERATURE = "sensor.temperature"


@pytest.fixture(autouse=True)
async def setup_entities(hass):
    """Set up component."""
    hass.config.units = METRIC_SYSTEM

    assert await async_setup_component(hass, "homeassistant", {})
    await hass.async_block_till_done()

    # Got the next code from tests/components/switch/test_init.py
    platform = getattr(hass.components, "test.switch")
    platform.init()
    assert await async_setup_component(
        hass, switch.DOMAIN, {"switch": {"platform": "test"}}
    )
    await hass.async_block_till_done()

    hass.states.async_set(SENSOR_TEMPERATURE, 48)
    await hass.async_block_till_done()

    mock_restore_cache(
        hass,
        (
            State(
                "water_heater.water_heater_restored",
                STATE_OFF,
                {ATTR_TEMPERATURE: "20"},
            ),
        ),
    )

    hass.state = CoreState.starting

    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                "my_water_heater": {
                    CONF_HEATER: SWITCH_HEATER,
                    CONF_SENSOR: SENSOR_TEMPERATURE,
                    CONF_TARGET_TEMP: 50,
                    CONF_TEMP_DELTA: 5,
                },
                "water_heater_restored": {
                    CONF_HEATER: SWITCH_HEATER,
                    CONF_SENSOR: SENSOR_TEMPERATURE,
                    CONF_TARGET_TEMP: 51,
                    CONF_TEMP_DELTA: 5,
                },
            }
        },
    )
    await hass.async_block_till_done()


async def test_setup_params(hass):
    """Test the initial parameters."""
    state = hass.states.get(WATER_HEATER)
    assert state.attributes.get("temperature") == 50
    assert state.attributes.get("current_temperature") == 48
    assert hass.states.get(SWITCH_HEATER).state == STATE_OFF


async def test_restore_state(hass):
    """Ensure states are restored on startup."""
    state = hass.states.get("water_heater.water_heater_restored")
    assert state.attributes.get("temperature") == 20
    assert state.state == STATE_OFF


async def test_turn_on_off_heater(hass):
    """Test heater switches on."""
    assert hass.states.get(SWITCH_HEATER).state == STATE_OFF

    state = hass.states.get(WATER_HEATER)
    assert state.attributes.get("temperature") == 50

    # increasing temperature turns the heater ON
    await common.async_set_temperature(hass, 55, WATER_HEATER)
    await hass.async_block_till_done()

    state = hass.states.get(WATER_HEATER)
    assert state.attributes.get("current_temperature") == 48
    assert state.attributes.get("temperature") == 55

    assert hass.states.get(SWITCH_HEATER).state == STATE_ON

    for temp in range(49, 50):
        hass.states.async_set(SENSOR_TEMPERATURE, temp)
        await hass.async_block_till_done()

    assert hass.states.get(SWITCH_HEATER).state == STATE_OFF


async def test_set_operation(hass):
    """Test operation change."""
    assert hass.states.get(SWITCH_HEATER).state == STATE_OFF

    # increasing temperature turns the heater ON
    await common.async_set_temperature(hass, 55, WATER_HEATER)
    await hass.async_block_till_done()

    assert hass.states.get(SWITCH_HEATER).state == STATE_ON
    await common.async_set_operation_mode(hass, STATE_OFF, WATER_HEATER)
    state = hass.states.get(WATER_HEATER)

    assert state.attributes.get("operation_mode") == STATE_OFF
    assert state.state == STATE_OFF


async def test_external_switch_interferance(hass):
    """Test external event changes heater switch."""
    # Start with Water Heater on
    assert hass.states.get(SWITCH_HEATER).state == STATE_OFF

    hass.states.async_set(SWITCH_HEATER, STATE_ON)
    await hass.async_block_till_done()

    assert hass.states.get(SWITCH_HEATER).state == STATE_ON
    state = hass.states.get(WATER_HEATER)

    assert state.attributes.get("operation_mode") == STATE_ON
    assert state.state == STATE_ON

    # Start with Water Heater off
    await common.async_set_operation_mode(hass, STATE_OFF, WATER_HEATER)
    await hass.async_block_till_done()

    hass.states.async_set(SWITCH_HEATER, STATE_ON)
    await hass.async_block_till_done()

    assert state.attributes.get("operation_mode") == STATE_ON
    assert state.state == STATE_ON


async def test_invalid_heater_and_sensor_events(hass):
    """Test invalid event changes in heater switch and temperature sensor."""
    state = hass.states.get(WATER_HEATER)
    assert state.attributes.get("operation_mode") == STATE_ON
    assert state.attributes.get("current_temperature") == 48

    # switch unavailable -> water_heater unavailable
    hass.states.async_set(SWITCH_HEATER, STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    state = hass.states.get(WATER_HEATER)
    assert state.state == STATE_UNAVAILABLE

    # bring back water_heater
    hass.states.async_set(SWITCH_HEATER, STATE_ON)
    await hass.async_block_till_done()

    state = hass.states.get(WATER_HEATER)
    assert state.state == STATE_ON

    # sensor unavailable -> failsafe
    hass.states.async_set(SENSOR_TEMPERATURE, STATE_UNAVAILABLE)
    await hass.async_block_till_done()

    state = hass.states.get(SWITCH_HEATER)
    assert state.state == STATE_OFF
    state = hass.states.get(WATER_HEATER)
    assert state.attributes.get("current_temperature") is None
