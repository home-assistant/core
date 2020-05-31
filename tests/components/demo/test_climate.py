"""The tests for the demo climate component."""

import pytest
import voluptuous as vol

from homeassistant.components.climate.const import (
    ATTR_AUX_HEAT,
    ATTR_CURRENT_HUMIDITY,
    ATTR_CURRENT_TEMPERATURE,
    ATTR_FAN_MODE,
    ATTR_HUMIDITY,
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODES,
    ATTR_MAX_HUMIDITY,
    ATTR_MAX_TEMP,
    ATTR_MIN_HUMIDITY,
    ATTR_MIN_TEMP,
    ATTR_PRESET_MODE,
    ATTR_SWING_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    CURRENT_HVAC_COOL,
    DOMAIN,
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    PRESET_AWAY,
    PRESET_ECO,
)
from homeassistant.const import ATTR_TEMPERATURE, STATE_OFF, STATE_ON
from homeassistant.setup import async_setup_component
from homeassistant.util.unit_system import METRIC_SYSTEM

from tests.components.climate import common

ENTITY_CLIMATE = "climate.hvac"
ENTITY_ECOBEE = "climate.ecobee"
ENTITY_HEATPUMP = "climate.heatpump"


@pytest.fixture(autouse=True)
async def setup_demo_climate(hass):
    """Initialize setup demo climate."""
    hass.config.units = METRIC_SYSTEM
    assert await async_setup_component(hass, DOMAIN, {"climate": {"platform": "demo"}})


def test_setup_params(hass):
    """Test the initial parameters."""
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.state == HVAC_MODE_COOL
    assert state.attributes.get(ATTR_TEMPERATURE) == 21
    assert state.attributes.get(ATTR_CURRENT_TEMPERATURE) == 22
    assert state.attributes.get(ATTR_FAN_MODE) == "On High"
    assert state.attributes.get(ATTR_HUMIDITY) == 67
    assert state.attributes.get(ATTR_CURRENT_HUMIDITY) == 54
    assert state.attributes.get(ATTR_SWING_MODE) == "Off"
    assert STATE_OFF == state.attributes.get(ATTR_AUX_HEAT)
    assert state.attributes.get(ATTR_HVAC_MODES) == [
        "off",
        "heat",
        "cool",
        "auto",
        "dry",
        "fan_only",
    ]


def test_default_setup_params(hass):
    """Test the setup with default parameters."""
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get(ATTR_MIN_TEMP) == 7
    assert state.attributes.get(ATTR_MAX_TEMP) == 35
    assert state.attributes.get(ATTR_MIN_HUMIDITY) == 30
    assert state.attributes.get(ATTR_MAX_HUMIDITY) == 99


async def test_set_only_target_temp_bad_attr(hass):
    """Test setting the target temperature without required attribute."""
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get(ATTR_TEMPERATURE) == 21

    with pytest.raises(vol.Invalid):
        await common.async_set_temperature(hass, None, ENTITY_CLIMATE)

    await hass.async_block_till_done()
    assert state.attributes.get(ATTR_TEMPERATURE) == 21


async def test_set_only_target_temp(hass):
    """Test the setting of the target temperature."""
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get(ATTR_TEMPERATURE) == 21

    await common.async_set_temperature(hass, 30, ENTITY_CLIMATE)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get(ATTR_TEMPERATURE) == 30.0


async def test_set_only_target_temp_with_convert(hass):
    """Test the setting of the target temperature."""
    state = hass.states.get(ENTITY_HEATPUMP)
    assert state.attributes.get(ATTR_TEMPERATURE) == 20

    await common.async_set_temperature(hass, 21, ENTITY_HEATPUMP)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_HEATPUMP)
    assert state.attributes.get(ATTR_TEMPERATURE) == 21.0


async def test_set_target_temp_range(hass):
    """Test the setting of the target temperature with range."""
    state = hass.states.get(ENTITY_ECOBEE)
    assert state.attributes.get(ATTR_TEMPERATURE) is None
    assert state.attributes.get(ATTR_TARGET_TEMP_LOW) == 21.0
    assert state.attributes.get(ATTR_TARGET_TEMP_HIGH) == 24.0

    await common.async_set_temperature(
        hass, target_temp_high=25, target_temp_low=20, entity_id=ENTITY_ECOBEE
    )
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ECOBEE)
    assert state.attributes.get(ATTR_TEMPERATURE) is None
    assert state.attributes.get(ATTR_TARGET_TEMP_LOW) == 20.0
    assert state.attributes.get(ATTR_TARGET_TEMP_HIGH) == 25.0


async def test_set_target_temp_range_bad_attr(hass):
    """Test setting the target temperature range without attribute."""
    state = hass.states.get(ENTITY_ECOBEE)
    assert state.attributes.get(ATTR_TEMPERATURE) is None
    assert state.attributes.get(ATTR_TARGET_TEMP_LOW) == 21.0
    assert state.attributes.get(ATTR_TARGET_TEMP_HIGH) == 24.0

    with pytest.raises(vol.Invalid):
        await common.async_set_temperature(
            hass,
            temperature=None,
            entity_id=ENTITY_ECOBEE,
            target_temp_low=None,
            target_temp_high=None,
        )
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ECOBEE)
    assert state.attributes.get(ATTR_TEMPERATURE) is None
    assert state.attributes.get(ATTR_TARGET_TEMP_LOW) == 21.0
    assert state.attributes.get(ATTR_TARGET_TEMP_HIGH) == 24.0


async def test_set_target_humidity_bad_attr(hass):
    """Test setting the target humidity without required attribute."""
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get(ATTR_HUMIDITY) == 67

    with pytest.raises(vol.Invalid):
        await common.async_set_humidity(hass, None, ENTITY_CLIMATE)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get(ATTR_HUMIDITY) == 67


async def test_set_target_humidity(hass):
    """Test the setting of the target humidity."""
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get(ATTR_HUMIDITY) == 67

    await common.async_set_humidity(hass, 64, ENTITY_CLIMATE)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get(ATTR_HUMIDITY) == 64.0


async def test_set_fan_mode_bad_attr(hass):
    """Test setting fan mode without required attribute."""
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get(ATTR_FAN_MODE) == "On High"

    with pytest.raises(vol.Invalid):
        await common.async_set_fan_mode(hass, None, ENTITY_CLIMATE)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get(ATTR_FAN_MODE) == "On High"


async def test_set_fan_mode(hass):
    """Test setting of new fan mode."""
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get(ATTR_FAN_MODE) == "On High"

    await common.async_set_fan_mode(hass, "On Low", ENTITY_CLIMATE)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get(ATTR_FAN_MODE) == "On Low"


async def test_set_swing_mode_bad_attr(hass):
    """Test setting swing mode without required attribute."""
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get(ATTR_SWING_MODE) == "Off"

    with pytest.raises(vol.Invalid):
        await common.async_set_swing_mode(hass, None, ENTITY_CLIMATE)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get(ATTR_SWING_MODE) == "Off"


async def test_set_swing(hass):
    """Test setting of new swing mode."""
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get(ATTR_SWING_MODE) == "Off"

    await common.async_set_swing_mode(hass, "Auto", ENTITY_CLIMATE)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get(ATTR_SWING_MODE) == "Auto"


async def test_set_hvac_bad_attr_and_state(hass):
    """Test setting hvac mode without required attribute.

    Also check the state.
    """
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get(ATTR_HVAC_ACTION) == CURRENT_HVAC_COOL
    assert state.state == HVAC_MODE_COOL

    with pytest.raises(vol.Invalid):
        await common.async_set_hvac_mode(hass, None, ENTITY_CLIMATE)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get(ATTR_HVAC_ACTION) == CURRENT_HVAC_COOL
    assert state.state == HVAC_MODE_COOL


async def test_set_hvac(hass):
    """Test setting of new hvac mode."""
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.state == HVAC_MODE_COOL

    await common.async_set_hvac_mode(hass, HVAC_MODE_HEAT, ENTITY_CLIMATE)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_CLIMATE)
    assert state.state == HVAC_MODE_HEAT


async def test_set_hold_mode_away(hass):
    """Test setting the hold mode away."""
    await common.async_set_preset_mode(hass, PRESET_AWAY, ENTITY_ECOBEE)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ECOBEE)
    assert state.attributes.get(ATTR_PRESET_MODE) == PRESET_AWAY


async def test_set_hold_mode_eco(hass):
    """Test setting the hold mode eco."""
    await common.async_set_preset_mode(hass, PRESET_ECO, ENTITY_ECOBEE)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ECOBEE)
    assert state.attributes.get(ATTR_PRESET_MODE) == PRESET_ECO


async def test_set_aux_heat_bad_attr(hass):
    """Test setting the auxiliary heater without required attribute."""
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get(ATTR_AUX_HEAT) == STATE_OFF

    with pytest.raises(vol.Invalid):
        await common.async_set_aux_heat(hass, None, ENTITY_CLIMATE)
    await hass.async_block_till_done()

    assert state.attributes.get(ATTR_AUX_HEAT) == STATE_OFF


async def test_set_aux_heat_on(hass):
    """Test setting the axillary heater on/true."""
    await common.async_set_aux_heat(hass, True, ENTITY_CLIMATE)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get(ATTR_AUX_HEAT) == STATE_ON


async def test_set_aux_heat_off(hass):
    """Test setting the auxiliary heater off/false."""
    await common.async_set_aux_heat(hass, False, ENTITY_CLIMATE)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get(ATTR_AUX_HEAT) == STATE_OFF


async def test_turn_on(hass):
    """Test turn on device."""
    await common.async_set_hvac_mode(hass, HVAC_MODE_OFF, ENTITY_CLIMATE)
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.state == HVAC_MODE_OFF

    await common.async_turn_on(hass, ENTITY_CLIMATE)
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.state == HVAC_MODE_HEAT


async def test_turn_off(hass):
    """Test turn on device."""
    await common.async_set_hvac_mode(hass, HVAC_MODE_HEAT, ENTITY_CLIMATE)
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.state == HVAC_MODE_HEAT

    await common.async_turn_off(hass, ENTITY_CLIMATE)
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.state == HVAC_MODE_OFF
