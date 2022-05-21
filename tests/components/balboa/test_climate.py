"""Tests of the climate entity of the balboa integration."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.climate.const import (
    ATTR_FAN_MODE,
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODES,
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    ATTR_PRESET_MODE,
    ATTR_PRESET_MODES,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_OFF,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, TEMP_FAHRENHEIT
from homeassistant.core import HomeAssistant

from . import init_integration

from tests.components.climate import common

FAN_SETTINGS = [
    FAN_OFF,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_HIGH,
]

HVAC_SETTINGS = [
    HVACMode.HEAT,
    HVACMode.OFF,
    HVACMode.AUTO,
]

ENTITY_CLIMATE = "climate.fakespa_climate"


async def test_spa_defaults(hass: HomeAssistant, client: MagicMock) -> None:
    """Test supported features flags."""
    await init_integration(hass)

    state = hass.states.get(ENTITY_CLIMATE)

    assert state
    assert (
        state.attributes["supported_features"]
        == ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
    )
    assert state.state == HVACMode.HEAT
    assert state.attributes[ATTR_MIN_TEMP] == 10.0
    assert state.attributes[ATTR_MAX_TEMP] == 40.0
    assert state.attributes[ATTR_PRESET_MODE] == "Ready"
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.IDLE


async def test_spa_defaults_fake_tscale(hass: HomeAssistant, client: MagicMock) -> None:
    """Test supported features flags."""
    client.get_tempscale.return_value = 1

    await init_integration(hass)

    state = hass.states.get(ENTITY_CLIMATE)

    assert state
    assert (
        state.attributes["supported_features"]
        == ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
    )
    assert state.state == HVACMode.HEAT
    assert state.attributes[ATTR_MIN_TEMP] == 10.0
    assert state.attributes[ATTR_MAX_TEMP] == 40.0
    assert state.attributes[ATTR_PRESET_MODE] == "Ready"
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.IDLE


async def test_spa_with_blower(hass: HomeAssistant, client: MagicMock) -> None:
    """Test supported features flags."""
    client.have_blower.return_value = True

    config_entry = await init_integration(hass)

    # force a refresh
    await client.new_data_cb()
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_CLIMATE)

    assert state
    assert (
        state.attributes["supported_features"]
        == ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.FAN_MODE
    )

    for fan_state in range(4):
        # set blower
        state = await _patch_blower(hass, config_entry, fan_state, client)
        assert state
        assert state.attributes[ATTR_FAN_MODE] == FAN_SETTINGS[fan_state]

    # test the nonsense checks
    for fan_state in (None, 70):  # type: ignore[assignment]
        state = await _patch_blower(hass, config_entry, fan_state, client)
        assert state
        assert state.attributes[ATTR_FAN_MODE] == FAN_OFF


async def test_spa_temperature(hass: HomeAssistant, client: MagicMock) -> None:
    """Test spa temperature settings."""

    config_entry = await init_integration(hass)

    # flip the spa into F
    # set temp to a valid number
    state = await _patch_spa_settemp(hass, config_entry, 0, 100.0, client)
    assert state
    assert state.attributes.get(ATTR_TEMPERATURE) == 38.0


async def test_spa_temperature_unit(hass: HomeAssistant, client: MagicMock) -> None:
    """Test temperature unit conversions."""

    with patch.object(hass.config.units, "temperature_unit", TEMP_FAHRENHEIT):
        config_entry = await init_integration(hass)

        state = await _patch_spa_settemp(hass, config_entry, 0, 15.4, client)
        assert state
        assert state.attributes.get(ATTR_TEMPERATURE) == 15.0


async def test_spa_hvac_modes(hass: HomeAssistant, client: MagicMock) -> None:
    """Test hvac modes."""

    config_entry = await init_integration(hass)

    # try out the different heat modes
    for heat_mode in range(2):
        state = await _patch_spa_heatmode(hass, config_entry, heat_mode, client)
        assert state
        modes = state.attributes.get(ATTR_HVAC_MODES)
        assert [HVACMode.AUTO, HVACMode.HEAT, HVACMode.OFF] == modes
        assert state.state == HVAC_SETTINGS[heat_mode]

    with pytest.raises(ValueError):
        await _patch_spa_heatmode(hass, config_entry, 2, client)


async def test_spa_hvac_action(hass: HomeAssistant, client: MagicMock) -> None:
    """Test setting of the HVAC action."""

    config_entry = await init_integration(hass)

    # try out the different heat states
    state = await _patch_spa_heatstate(hass, config_entry, 1, client)
    assert state
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.HEATING

    state = await _patch_spa_heatstate(hass, config_entry, 0, client)
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.IDLE


async def test_spa_preset_modes(hass: HomeAssistant, client: MagicMock) -> None:
    """Test the various preset modes."""

    await init_integration(hass)

    state = hass.states.get(ENTITY_CLIMATE)
    assert state
    modes = state.attributes.get(ATTR_PRESET_MODES)
    assert ["Ready", "Rest", "Ready in Rest"] == modes

    # Put it in Ready and Rest
    modelist = ["Ready", "Rest"]
    for mode in modelist:
        client.heatmode = modelist.index(mode)
        await common.async_set_preset_mode(hass, mode, ENTITY_CLIMATE)
        await client.new_data_cb()
        await hass.async_block_till_done()

        state = hass.states.get(ENTITY_CLIMATE)
        assert state
        assert state.attributes[ATTR_PRESET_MODE] == mode

    # put it in RNR and test assertion
    client.heatmode = 2

    with pytest.raises(ValueError):
        await common.async_set_preset_mode(hass, 2, ENTITY_CLIMATE)


# Helpers
async def _patch_blower(hass, config_entry, fan_state, client):
    """Patch the blower state."""
    client.get_blower.return_value = fan_state

    if fan_state is not None and fan_state <= len(FAN_SETTINGS):
        await common.async_set_fan_mode(hass, FAN_SETTINGS[fan_state])
    await client.new_data_cb()
    await hass.async_block_till_done()

    return hass.states.get(ENTITY_CLIMATE)


async def _patch_spa_settemp(hass, config_entry, tscale, settemp, client):
    """Patch the settemp."""
    client.get_tempscale.return_value = tscale
    client.get_settemp.return_value = settemp

    await common.async_set_temperature(
        hass, temperature=settemp, entity_id=ENTITY_CLIMATE
    )
    await client.new_data_cb()
    await hass.async_block_till_done()

    return hass.states.get(ENTITY_CLIMATE)


async def _patch_spa_heatmode(hass, config_entry, heat_mode, client):
    """Patch the heatmode."""
    client.heatmode = heat_mode

    await common.async_set_hvac_mode(hass, HVAC_SETTINGS[heat_mode], ENTITY_CLIMATE)
    await client.new_data_cb()
    await hass.async_block_till_done()

    return hass.states.get(ENTITY_CLIMATE)


async def _patch_spa_heatstate(hass, config_entry, heat_state, client):
    """Patch the heatmode."""
    client.get_heatstate.return_value = heat_state

    await common.async_set_hvac_mode(hass, HVAC_SETTINGS[heat_state], ENTITY_CLIMATE)
    await client.new_data_cb()
    await hass.async_block_till_done()

    return hass.states.get(ENTITY_CLIMATE)
