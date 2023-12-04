"""Test the Generic Thermostat component setup process."""
import pytest
import voluptuous as vol

from homeassistant.components import input_boolean, switch
from homeassistant.components.climate import DOMAIN, HVACMode
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util.unit_system import METRIC_SYSTEM

from tests.common import assert_setup_component
from tests.components.climate import common
from tests.components.generic_thermostat.const import (
    ENT_SENSOR,
    ENT_SWITCH,
    ENTITY,
    MAX_TEMP,
    MIN_TEMP,
    TARGET_TEMP,
    TARGET_TEMP_STEP,
)
from tests.components.generic_thermostat.shared import _setup_sensor, _setup_switch


async def test_setup_missing_conf(hass: HomeAssistant) -> None:
    """Test set up heat_control with missing config values."""
    config = {
        "platform": "generic_thermostat",
        "name": "test",
        "target_sensor": ENT_SENSOR,
    }
    with assert_setup_component(0):
        await async_setup_component(hass, "climate", {"climate": config})


async def test_valid_conf(hass: HomeAssistant) -> None:
    """Test set up generic_thermostat with valid config values."""
    assert await async_setup_component(
        hass,
        "climate",
        {
            "climate": {
                "platform": "generic_thermostat",
                "name": "test",
                "heater": ENT_SWITCH,
                "target_sensor": ENT_SENSOR,
            }
        },
    )


@pytest.fixture
async def setup_comp_1(hass):
    """Initialize components."""
    hass.config.units = METRIC_SYSTEM
    assert await async_setup_component(hass, "homeassistant", {})
    await hass.async_block_till_done()


async def test_heater_input_boolean(hass: HomeAssistant, setup_comp_1) -> None:
    """Test heater switching input_boolean."""
    heater_switch = "input_boolean.test"
    assert await async_setup_component(
        hass, input_boolean.DOMAIN, {"input_boolean": {"test": None}}
    )

    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            "climate": {
                "platform": "generic_thermostat",
                "name": "test",
                "heater": heater_switch,
                "target_sensor": ENT_SENSOR,
                "initial_hvac_mode": HVACMode.HEAT,
            }
        },
    )
    await hass.async_block_till_done()

    assert hass.states.get(heater_switch).state == STATE_OFF

    _setup_sensor(hass, 18)
    await hass.async_block_till_done()
    await common.async_set_temperature(hass, 23)
    await hass.async_block_till_done()

    assert hass.states.get(heater_switch).state == STATE_ON


async def test_heater_switch(
    hass: HomeAssistant, setup_comp_1, enable_custom_integrations: None
) -> None:
    """Test heater switching test switch."""
    platform = getattr(hass.components, "test.switch")
    platform.init()
    switch_1 = platform.ENTITIES[1]
    assert await async_setup_component(
        hass, switch.DOMAIN, {"switch": {"platform": "test"}}
    )
    await hass.async_block_till_done()
    heater_switch = switch_1.entity_id

    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            "climate": {
                "platform": "generic_thermostat",
                "name": "test",
                "heater": heater_switch,
                "target_sensor": ENT_SENSOR,
                "initial_hvac_mode": HVACMode.HEAT,
            }
        },
    )

    await hass.async_block_till_done()
    assert hass.states.get(heater_switch).state == STATE_OFF

    _setup_sensor(hass, 18)
    await common.async_set_temperature(hass, 23)
    await hass.async_block_till_done()

    assert hass.states.get(heater_switch).state == STATE_ON


async def test_unique_id(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, setup_comp_1
) -> None:
    """Test setting a unique ID."""
    unique_id = "some_unique_id"
    _setup_sensor(hass, 18)
    _setup_switch(hass, True)
    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            "climate": {
                "platform": "generic_thermostat",
                "name": "test",
                "heater": ENT_SWITCH,
                "target_sensor": ENT_SENSOR,
                "unique_id": unique_id,
            }
        },
    )
    await hass.async_block_till_done()

    entry = entity_registry.async_get(ENTITY)
    assert entry
    assert entry.unique_id == unique_id


async def test_setup_defaults_to_unknown(hass: HomeAssistant) -> None:
    """Test the setting of defaults to unknown."""
    hass.config.units = METRIC_SYSTEM
    await async_setup_component(
        hass,
        DOMAIN,
        {
            "climate": {
                "platform": "generic_thermostat",
                "name": "test",
                "cold_tolerance": 2,
                "hot_tolerance": 4,
                "heater": ENT_SWITCH,
                "target_sensor": ENT_SENSOR,
                "away_temp": 16,
            }
        },
    )
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY).state == HVACMode.OFF


async def test_setup_gets_current_temp_from_sensor(hass: HomeAssistant) -> None:
    """Test that current temperature is updated on entity addition."""
    hass.config.units = METRIC_SYSTEM
    _setup_sensor(hass, 18)
    await hass.async_block_till_done()
    await async_setup_component(
        hass,
        DOMAIN,
        {
            "climate": {
                "platform": "generic_thermostat",
                "name": "test",
                "cold_tolerance": 2,
                "hot_tolerance": 4,
                "heater": ENT_SWITCH,
                "target_sensor": ENT_SENSOR,
                "away_temp": 16,
            }
        },
    )
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY).attributes["current_temperature"] == 18


async def test_default_setup_params(hass: HomeAssistant, setup_comp_2) -> None:
    """Test the setup with default parameters."""
    state = hass.states.get(ENTITY)
    assert state.attributes.get("min_temp") == 7
    assert state.attributes.get("max_temp") == 35
    assert state.attributes.get("temperature") == 7
    assert state.attributes.get("target_temp_step") == 0.1


async def test_get_hvac_modes(hass: HomeAssistant, setup_comp_2) -> None:
    """Test that the operation list returns the correct modes."""
    state = hass.states.get(ENTITY)
    modes = state.attributes.get("hvac_modes")
    assert modes == [HVACMode.HEAT, HVACMode.OFF]


async def test_set_target_temp(hass: HomeAssistant, setup_comp_2) -> None:
    """Test the setting of the target temperature."""
    await common.async_set_temperature(hass, 30)
    state = hass.states.get(ENTITY)
    assert state.attributes.get("temperature") == 30.0
    with pytest.raises(vol.Invalid):
        await common.async_set_temperature(hass, None)
    state = hass.states.get(ENTITY)
    assert state.attributes.get("temperature") == 30.0


async def test_custom_setup_params(hass: HomeAssistant) -> None:
    """Test the setup with custom parameters."""
    result = await async_setup_component(
        hass,
        DOMAIN,
        {
            "climate": {
                "platform": "generic_thermostat",
                "name": "test",
                "heater": ENT_SWITCH,
                "target_sensor": ENT_SENSOR,
                "min_temp": MIN_TEMP,
                "max_temp": MAX_TEMP,
                "target_temp": TARGET_TEMP,
                "target_temp_step": 0.5,
            }
        },
    )
    assert result
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY)
    assert state.attributes.get("min_temp") == MIN_TEMP
    assert state.attributes.get("max_temp") == MAX_TEMP
    assert state.attributes.get("temperature") == TARGET_TEMP
    assert state.attributes.get("target_temp_step") == TARGET_TEMP_STEP
