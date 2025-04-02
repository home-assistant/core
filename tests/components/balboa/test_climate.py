"""Tests of the climate entity of the balboa integration."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from pybalboa import SpaControl
from pybalboa.enums import HeatMode, OffLowMediumHighState
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    ATTR_FAN_MODES,
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
from homeassistant.const import ATTR_TEMPERATURE, Platform
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from . import client_update, init_integration

from tests.common import MockConfigEntry, snapshot_platform
from tests.components.climate import common

HVAC_SETTINGS = [
    HVACMode.HEAT,
    HVACMode.OFF,
    HVACMode.AUTO,
]

ENTITY_CLIMATE = "climate.fakespa"


async def test_climate(
    hass: HomeAssistant,
    client: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test spa climate."""
    with patch("homeassistant.components.balboa.PLATFORMS", [Platform.CLIMATE]):
        entry = await init_integration(hass)

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


async def test_spa_defaults_fake_tscale(
    hass: HomeAssistant, client: MagicMock, integration: MockConfigEntry
) -> None:
    """Test supported features flags."""
    client.temperature_unit = 1

    state = hass.states.get(ENTITY_CLIMATE)

    assert state
    assert (
        state.attributes["supported_features"]
        == ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )
    assert state.state == HVACMode.HEAT
    assert state.attributes[ATTR_MIN_TEMP] == 10.0
    assert state.attributes[ATTR_MAX_TEMP] == 40.0
    assert state.attributes[ATTR_PRESET_MODE] == "ready"
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.IDLE


async def test_spa_temperature(
    hass: HomeAssistant, client: MagicMock, integration: MockConfigEntry
) -> None:
    """Test spa temperature settings."""
    client.temperature_minimum = 110
    client.temperature_maximum = 250
    # flip the spa into F
    # set temp to a valid number
    state = await _patch_spa_settemp(hass, client, 0, 100)
    assert state.attributes.get(ATTR_TEMPERATURE) == 38.0


async def test_spa_temperature_unit(
    hass: HomeAssistant, client: MagicMock, integration: MockConfigEntry
) -> None:
    """Test temperature unit conversions."""
    hass.config.units = US_CUSTOMARY_SYSTEM

    state = await _patch_spa_settemp(hass, client, 0, 15.4)
    assert state.attributes.get(ATTR_TEMPERATURE) == 15.0


async def test_spa_hvac_modes(
    hass: HomeAssistant, client: MagicMock, integration: MockConfigEntry
) -> None:
    """Test hvac modes."""
    # try out the different heat modes
    for heat_mode in list(HeatMode)[:2]:
        state = await _patch_spa_heatmode(hass, client, heat_mode)
        modes = state.attributes.get(ATTR_HVAC_MODES)
        assert modes == [HVACMode.HEAT, HVACMode.OFF]
        assert state.state == HVAC_SETTINGS[heat_mode]


async def test_spa_hvac_action(
    hass: HomeAssistant, client: MagicMock, integration: MockConfigEntry
) -> None:
    """Test setting of the HVAC action."""
    # try out the different heat states
    state = await _patch_spa_heatstate(hass, client, 0)
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.OFF

    state = await _patch_spa_heatstate(hass, client, 1)
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.HEATING

    state = await _patch_spa_heatstate(hass, client, 2)
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.IDLE


async def test_spa_preset_modes(
    hass: HomeAssistant, client: MagicMock, integration: MockConfigEntry
) -> None:
    """Test the various preset modes."""
    state = hass.states.get(ENTITY_CLIMATE)
    assert state
    modes = state.attributes.get(ATTR_PRESET_MODES)
    assert modes == ["ready", "rest"]

    # Put it in Ready and Rest
    modelist = ["ready", "rest"]
    for mode in modelist:
        client.heat_mode.state = HeatMode[mode.upper()]
        await common.async_set_preset_mode(hass, mode, ENTITY_CLIMATE)

        state = await client_update(hass, client, ENTITY_CLIMATE)
        assert state
        assert state.attributes[ATTR_PRESET_MODE] == mode

    with pytest.raises(ServiceValidationError):
        await common.async_set_preset_mode(hass, 2, ENTITY_CLIMATE)

    # put it in RNR and test assertion
    client.heat_mode.state = HeatMode.READY_IN_REST
    state = await client_update(hass, client, ENTITY_CLIMATE)
    assert state
    assert state.attributes[ATTR_PRESET_MODE] == "ready_in_rest"


async def test_spa_with_blower(hass: HomeAssistant, client: MagicMock) -> None:
    """Test supported features flags."""
    blower = MagicMock(SpaControl)
    blower.state = OffLowMediumHighState.OFF
    blower.options = list(OffLowMediumHighState)
    client.blowers = [blower]

    await init_integration(hass)

    state = hass.states.get(ENTITY_CLIMATE)

    assert state
    assert (
        state.attributes["supported_features"]
        == ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )
    assert state.state == HVACMode.HEAT
    assert state.attributes[ATTR_MIN_TEMP] == 10.0
    assert state.attributes[ATTR_MAX_TEMP] == 40.0
    assert state.attributes[ATTR_PRESET_MODE] == "ready"
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.IDLE
    assert state.attributes[ATTR_FAN_MODES] == ["off", "low", "medium", "high"]
    assert state.attributes[ATTR_FAN_MODE] == FAN_OFF

    for fan_mode in (FAN_LOW, FAN_MEDIUM, FAN_HIGH):
        client.blowers[0].set_state.reset_mock()
        state = await _patch_blower(hass, client, fan_mode)
        assert state.attributes[ATTR_FAN_MODE] == fan_mode
        client.blowers[0].set_state.assert_called_once()


# Helpers


async def _patch_blower(hass: HomeAssistant, client: MagicMock, fan_mode: str) -> State:
    """Patch the blower state."""
    client.blowers[0].state = OffLowMediumHighState[fan_mode.upper()]
    await common.async_set_fan_mode(hass, fan_mode)
    return await client_update(hass, client, ENTITY_CLIMATE)


async def _patch_spa_settemp(
    hass: HomeAssistant, client: MagicMock, tscale: int, settemp: float
) -> State:
    """Patch the settemp."""
    client.temperature_unit = tscale
    client.target_temperature = settemp
    await common.async_set_temperature(
        hass, temperature=settemp, entity_id=ENTITY_CLIMATE
    )
    return await client_update(hass, client, ENTITY_CLIMATE)


async def _patch_spa_heatmode(
    hass: HomeAssistant, client: MagicMock, heat_mode: int
) -> State:
    """Patch the heatmode."""
    client.heat_mode.state = heat_mode
    await common.async_set_hvac_mode(hass, HVAC_SETTINGS[heat_mode], ENTITY_CLIMATE)
    return await client_update(hass, client, ENTITY_CLIMATE)


async def _patch_spa_heatstate(
    hass: HomeAssistant, client: MagicMock, heat_state: int
) -> State:
    """Patch the heatmode."""
    client.heat_state = heat_state
    await common.async_set_hvac_mode(hass, HVAC_SETTINGS[heat_state], ENTITY_CLIMATE)
    return await client_update(hass, client, ENTITY_CLIMATE)
