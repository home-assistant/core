"""Tests of the climate entity of the balboa integration."""

from unittest.mock import patch

from homeassistant.components.balboa.const import DOMAIN as BALBOA_DOMAIN, SIGNAL_UPDATE
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
from homeassistant.helpers.dispatcher import async_dispatcher_send
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

    await _setup_climate_test(hass)

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

    with patch(
        "homeassistant.components.balboa.BalboaSpaWifi.have_blower", return_value=True
    ):
        config_entry = await _setup_climate_test(hass)

    # force a refresh
    async_dispatcher_send(hass, SIGNAL_UPDATE.format(config_entry.entry_id))
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_CLIMATE)

    assert (
        state.attributes["supported_features"]
        == SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE | SUPPORT_FAN_MODE
    )

    for fan_state in range(4):
        # set blower
        state = await _patch_blower(hass, config_entry, fan_state)
        assert state.attributes[ATTR_FAN_MODE] == FAN_SETTINGS[fan_state]

    # test the nonsense checks
    for fan_state in (None, 70):
        state = await _patch_blower(hass, config_entry, fan_state)
        assert state.attributes[ATTR_FAN_MODE] == FAN_OFF


async def test_spa_temperature(hass: HomeAssistant):
    """Test spa temperature settings."""

    config_entry = await _setup_climate_test(hass)

    # flip the spa into celsius
    # set temp to a valid number (and validate we return precision)
    state = await _patch_spa_settemp(hass, config_entry, 1, 37.4)
    assert state.attributes.get(ATTR_TEMPERATURE) == 37.5

    # flip the spa into F
    # set temp to a valid number
    state = await _patch_spa_settemp(hass, config_entry, 0, 100.0)
    assert state.attributes.get(ATTR_TEMPERATURE) == 38.0


async def test_spa_temperature_unit(hass: HomeAssistant):
    """Test temperature unit conversions."""

    with patch.object(hass.config.units, "temperature_unit", TEMP_FAHRENHEIT):
        config_entry = await _setup_climate_test(hass)

        state = await _patch_spa_settemp(hass, config_entry, 0, 15.4)
        assert state.attributes.get(ATTR_TEMPERATURE) == 15.0

        # flip the spa to Celsius and try again
        state = await _patch_spa_settemp(hass, config_entry, 1, 15.4)
        assert state.attributes.get(ATTR_TEMPERATURE) == 60.0


async def test_spa_hvac_modes(hass: HomeAssistant):
    """Test hvac modes."""

    config_entry = await _setup_climate_test(hass)

    # try out the different heat modes
    for heat_mode in range(3):
        state = await _patch_spa_heatmode(hass, config_entry, heat_mode)
        modes = state.attributes.get(ATTR_HVAC_MODES)
        if heat_mode == 2:
            assert [HVAC_MODE_HEAT, HVAC_MODE_OFF, HVAC_MODE_AUTO] == modes
        else:
            assert [HVAC_MODE_HEAT, HVAC_MODE_OFF] == modes
        assert state.state == HVAC_SETTINGS[heat_mode]


async def test_spa_hvac_action(hass: HomeAssistant):
    """Test setting of the HVAC action."""

    config_entry = await _setup_climate_test(hass)

    # try out the different heat states
    state = await _patch_spa_heatstate(hass, config_entry, 1)
    assert state.attributes[ATTR_HVAC_ACTION] == CURRENT_HVAC_HEAT

    state = await _patch_spa_heatstate(hass, config_entry, 0)
    assert state.attributes[ATTR_HVAC_ACTION] == CURRENT_HVAC_IDLE


async def test_spa_preset_modes(hass: HomeAssistant):
    """Test the various preset modes."""

    config_entry = await _setup_climate_test(hass)

    state = hass.states.get(ENTITY_CLIMATE)
    modes = state.attributes.get(ATTR_PRESET_MODES)
    assert ["Ready", "Rest"] == modes

    # Force the spa into Ready in Rest
    state = await _patch_spa_heatmode(hass, config_entry, 2)
    modes = state.attributes.get(ATTR_PRESET_MODES)
    assert ["Ready", "Rest", "Ready in Rest"] == modes

    # Put it back in Ready
    await common.async_set_preset_mode(hass, "Ready", ENTITY_CLIMATE)
    async_dispatcher_send(hass, SIGNAL_UPDATE.format(config_entry.entry_id))
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes[ATTR_PRESET_MODE] == "Ready"


# Helpers
async def _patch_blower(hass, config_entry, fan_state):
    """Patch the blower state."""
    with patch(
        "homeassistant.components.balboa.BalboaSpaWifi.get_blower",
        return_value=fan_state,
    ):
        if fan_state is not None and fan_state <= len(FAN_SETTINGS):
            await common.async_set_fan_mode(hass, FAN_SETTINGS[fan_state])
        async_dispatcher_send(hass, SIGNAL_UPDATE.format(config_entry.entry_id))
        await hass.async_block_till_done()

    return hass.states.get(ENTITY_CLIMATE)


async def _patch_spa_settemp(hass, config_entry, tscale, settemp):
    """Patch the settemp."""
    with patch(
        "homeassistant.components.balboa.BalboaSpaWifi.get_tempscale",
        return_value=tscale,
    ), patch(
        "homeassistant.components.balboa.BalboaSpaWifi.get_settemp",
        return_value=settemp,
    ):
        await common.async_set_temperature(
            hass, temperature=settemp, entity_id=ENTITY_CLIMATE
        )
        async_dispatcher_send(hass, SIGNAL_UPDATE.format(config_entry.entry_id))
        await hass.async_block_till_done()

    return hass.states.get(ENTITY_CLIMATE)


async def _patch_spa_heatmode(hass, config_entry, heat_mode):
    """Patch the heatmode."""
    with patch(
        "homeassistant.components.balboa.BalboaSpaWifi.get_heatmode",
        return_value=heat_mode,
    ):
        await common.async_set_hvac_mode(hass, HVAC_SETTINGS[heat_mode], ENTITY_CLIMATE)
        async_dispatcher_send(hass, SIGNAL_UPDATE.format(config_entry.entry_id))
        await hass.async_block_till_done()

    return hass.states.get(ENTITY_CLIMATE)


async def _patch_spa_heatstate(hass, config_entry, heat_state):
    """Patch the heatmode."""
    with patch(
        "homeassistant.components.balboa.BalboaSpaWifi.get_heatstate",
        return_value=heat_state,
    ):
        await common.async_set_hvac_mode(
            hass, HVAC_SETTINGS[heat_state], ENTITY_CLIMATE
        )
        async_dispatcher_send(hass, SIGNAL_UPDATE.format(config_entry.entry_id))
        await hass.async_block_till_done()

    return hass.states.get(ENTITY_CLIMATE)


async def _setup_climate_test(hass):
    """Prepare the test."""
    config_entry = await init_integration_mocked(hass)
    await async_setup_component(hass, BALBOA_DOMAIN, config_entry)
    await hass.async_block_till_done()

    return config_entry
