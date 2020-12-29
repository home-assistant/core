"""Tests for Generic Water heater."""
import pytest

from homeassistant.components import switch, water_heater
from homeassistant.const import SERVICE_TURN_OFF, SERVICE_TURN_ON, STATE_OFF, STATE_ON
from homeassistant.core import DOMAIN as HASS_DOMAIN, callback
from homeassistant.setup import async_setup_component
from homeassistant.util.unit_system import METRIC_SYSTEM

from tests.components.water_heater import common

WATER_HEATER = "water_heater.generic_water_heater"
SWITCH_HEATER = "switch.ac_2"
SENSOR_TEMPERATURE = "sensor.temperature"


def _setup_switch(hass, state):
    """Set up the test switch."""
    hass.states.async_set(SWITCH_HEATER, state)
    calls = []

    @callback
    def log_call(call):
        """Log service calls."""
        calls.append(call)

    hass.services.async_register(HASS_DOMAIN, SERVICE_TURN_ON, log_call)
    hass.services.async_register(HASS_DOMAIN, SERVICE_TURN_OFF, log_call)

    return calls


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

    assert await async_setup_component(
        hass,
        water_heater.DOMAIN,
        {
            "water_heater": {
                "platform": "generic",
                "heater": SWITCH_HEATER,
                "temperature_sensor": SENSOR_TEMPERATURE,
                "target_temperature": 50,
                "delta_temperature": 5,
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

    hass.states.async_set(SENSOR_TEMPERATURE, 53)
    await hass.async_block_till_done()

    assert hass.states.get(SWITCH_HEATER).state == STATE_OFF


async def test_set_operation(hass):
    """Test operation change."""
    assert hass.states.get(SWITCH_HEATER).state == STATE_OFF

    # increasing temperature turns the heater ON
    await common.async_set_temperature(hass, 55, WATER_HEATER)
    await hass.async_block_till_done()

    assert hass.states.get(SWITCH_HEATER).state == STATE_ON
    await common.async_set_operation_mode(hass, "off", WATER_HEATER)
    state = hass.states.get(WATER_HEATER)

    assert state.attributes.get("operation_mode") == "off"
    assert state.state == "off"


async def test_external_switch_interferance(hass):
    """Test external event changes heater switch."""
    assert hass.states.get(SWITCH_HEATER).state == STATE_OFF

    # increasing temperature turns the heater ON
    hass.states.async_set(SWITCH_HEATER, STATE_ON)
    await hass.async_block_till_done()

    assert hass.states.get(SWITCH_HEATER).state == STATE_ON
    state = hass.states.get(WATER_HEATER)

    assert state.attributes.get("operation_mode") == "on"
    assert state.state == "on"
