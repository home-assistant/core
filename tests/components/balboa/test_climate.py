"""Tests of the climate entity of the balboa integration."""

from unittest.mock import patch

from homeassistant.components.balboa.const import DOMAIN as BALBOA_DOMAIN
from homeassistant.components.climate.const import (
    ATTR_FAN_MODE,
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODES,
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    ATTR_PRESET_MODE,
    ATTR_PRESET_MODES,
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_OFF,
    HVAC_MODE_AUTO,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    SUPPORT_FAN_MODE,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import ATTR_TEMPERATURE, TEMP_FAHRENHEIT
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import init_integration_mocked

from tests.components.climate import common

FAN_SETTINGS = [
    FAN_OFF,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_HIGH,
]

HVAC_SETTINGS = [
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    HVAC_MODE_AUTO,
]

ENTITY_CLIMATE = "climate.fakespa_climate"


async def test_spa_defaults(hass: HomeAssistant):
    """Test supported features flags."""

    config_entry = await init_integration_mocked(hass)

    await async_setup_component(hass, BALBOA_DOMAIN, config_entry)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_CLIMATE)

    assert (
        state.attributes["supported_features"]
        == SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE
    )
    assert state.state == HVAC_MODE_HEAT
    assert state.attributes[ATTR_MIN_TEMP] == 10.0
    assert state.attributes[ATTR_MAX_TEMP] == 26.5
    assert state.attributes[ATTR_PRESET_MODE] == "Ready"
    assert state.attributes[ATTR_HVAC_ACTION] == CURRENT_HVAC_IDLE


async def test_spa_with_blower(hass: HomeAssistant):
    """Test supported features flags."""

    config_entry = await init_integration_mocked(hass)

    await async_setup_component(hass, BALBOA_DOMAIN, config_entry)
    await hass.async_block_till_done()

    spa = hass.data[BALBOA_DOMAIN][config_entry.entry_id]
    spa.blower = True

    # force a refresh
    await spa.int_new_data_cb()
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_CLIMATE)

    assert (
        state.attributes["supported_features"]
        == SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE | SUPPORT_FAN_MODE
    )

    for fan_state in range(4):
        # set blower
        spa.blower_status = fan_state
        await common.async_set_fan_mode(hass, FAN_SETTINGS[fan_state])
        await spa.int_new_data_cb()
        await hass.async_block_till_done()

        state = hass.states.get(ENTITY_CLIMATE)
        assert state.attributes[ATTR_FAN_MODE] == FAN_SETTINGS[fan_state]

    # test the nonsense checks
    for fan_state in (None, 70):
        spa.blower_status = fan_state
        await spa.int_new_data_cb()
        await hass.async_block_till_done()

        state = hass.states.get(ENTITY_CLIMATE)
        assert state.attributes[ATTR_FAN_MODE] == FAN_OFF


async def test_spa_temperature(hass: HomeAssistant):
    """Test spa temperature settings."""

    config_entry = await init_integration_mocked(hass)

    await async_setup_component(hass, BALBOA_DOMAIN, config_entry)
    await hass.async_block_till_done()

    spa = hass.data[BALBOA_DOMAIN][config_entry.entry_id]

    # flip the spa into celsius
    spa.tempscale = 1

    # set temp to a valid number (and validate we return precision)
    spa.settemp = 15.4
    await common.async_set_temperature(hass, temperature=15.4, entity_id=ENTITY_CLIMATE)
    await spa.int_new_data_cb()
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_CLIMATE)

    assert state.attributes.get(ATTR_TEMPERATURE) == 15.5

    # flip the spa into F
    spa.tempscale = 0

    # set temp to a valid number
    spa.settemp = 100.0
    await common.async_set_temperature(
        hass, temperature=100.0, entity_id=ENTITY_CLIMATE
    )
    await spa.int_new_data_cb()
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_CLIMATE)

    assert state.attributes.get(ATTR_TEMPERATURE) == 38.0


async def test_spa_temperature_unit(hass: HomeAssistant):
    """Test temperature unit conversions."""

    with patch.object(hass.config.units, "temperature_unit", TEMP_FAHRENHEIT):
        config_entry = await init_integration_mocked(hass)

        await async_setup_component(hass, BALBOA_DOMAIN, config_entry)
        await hass.async_block_till_done()

        spa = hass.data[BALBOA_DOMAIN][config_entry.entry_id]

        spa.settemp = 15.4
        await common.async_set_temperature(
            hass, temperature=15.4, entity_id=ENTITY_CLIMATE
        )
        await spa.int_new_data_cb()
        await hass.async_block_till_done()
        state = hass.states.get(ENTITY_CLIMATE)

        assert state.attributes.get(ATTR_TEMPERATURE) == 15.0

        # flip the spa to Celsius and try again
        spa.settemp = 15.4
        spa.tempscale = 1
        await common.async_set_temperature(
            hass, temperature=15.4, entity_id=ENTITY_CLIMATE
        )
        await spa.int_new_data_cb()
        await hass.async_block_till_done()
        state = hass.states.get(ENTITY_CLIMATE)

        assert state.attributes.get(ATTR_TEMPERATURE) == 60.0


async def test_spa_hvac_modes(hass: HomeAssistant):
    """Test hvac modes."""

    config_entry = await init_integration_mocked(hass)

    await async_setup_component(hass, BALBOA_DOMAIN, config_entry)
    await hass.async_block_till_done()

    spa = hass.data[BALBOA_DOMAIN][config_entry.entry_id]

    # try out the different heat modes
    for heat_mode in range(3):
        spa.heatmode = heat_mode
        await common.async_set_hvac_mode(hass, HVAC_SETTINGS[heat_mode], ENTITY_CLIMATE)
        await spa.int_new_data_cb()
        await hass.async_block_till_done()
        state = hass.states.get(ENTITY_CLIMATE)
        modes = state.attributes.get(ATTR_HVAC_MODES)
        if heat_mode == 2:
            assert [HVAC_MODE_HEAT, HVAC_MODE_OFF, HVAC_MODE_AUTO] == modes
        else:
            assert [HVAC_MODE_HEAT, HVAC_MODE_OFF] == modes
        assert state.state == HVAC_SETTINGS[heat_mode]


async def test_spa_hvac_action(hass: HomeAssistant):
    """Test setting of the HVAC action."""

    config_entry = await init_integration_mocked(hass)

    await async_setup_component(hass, BALBOA_DOMAIN, config_entry)
    await hass.async_block_till_done()

    spa = hass.data[BALBOA_DOMAIN][config_entry.entry_id]

    # try out the different heat states
    spa.heatstate = 1
    await spa.int_new_data_cb()
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_CLIMATE)

    assert state.attributes[ATTR_HVAC_ACTION] == CURRENT_HVAC_HEAT

    spa.heatstate = 0
    await spa.int_new_data_cb()
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_CLIMATE)

    assert state.attributes[ATTR_HVAC_ACTION] == CURRENT_HVAC_IDLE


async def test_spa_preset_modes(hass: HomeAssistant):
    """Test the various preset modes."""

    config_entry = await init_integration_mocked(hass)

    await async_setup_component(hass, BALBOA_DOMAIN, config_entry)
    await hass.async_block_till_done()

    spa = hass.data[BALBOA_DOMAIN][config_entry.entry_id]

    state = hass.states.get(ENTITY_CLIMATE)
    modes = state.attributes.get(ATTR_PRESET_MODES)
    assert ["Ready", "Rest"] == modes

    # Force the spa into Ready in Rest
    spa.heatmode = 2
    await spa.int_new_data_cb()
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_CLIMATE)
    modes = state.attributes.get(ATTR_PRESET_MODES)
    assert spa.get_heatmode_stringlist() == modes

    # Put it back in Ready
    spa.heatmode = 0
    await common.async_set_preset_mode(hass, "Ready", ENTITY_CLIMATE)
    await spa.int_new_data_cb()
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes[ATTR_PRESET_MODE] == "Ready"
