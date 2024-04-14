"""The test for the Coolmaster climate platform."""

from __future__ import annotations

from pycoolmasternet_async import SWING_MODES
import pytest

from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_FAN_MODE,
    ATTR_FAN_MODES,
    ATTR_HVAC_MODE,
    ATTR_HVAC_MODES,
    ATTR_SWING_MODE,
    ATTR_SWING_MODES,
    DOMAIN as CLIMATE_DOMAIN,
    FAN_HIGH,
    FAN_LOW,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_SWING_MODE,
    SERVICE_SET_TEMPERATURE,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.components.coolmaster.climate import FAN_MODES
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_SUPPORTED_FEATURES,
    ATTR_TEMPERATURE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError


async def test_climate_state(
    hass: HomeAssistant,
    load_int: ConfigEntry,
) -> None:
    """Test the Coolmaster climate state."""
    assert hass.states.get("climate.l1_100").state == HVACMode.OFF
    assert hass.states.get("climate.l1_101").state == HVACMode.HEAT


async def test_climate_friendly_name(
    hass: HomeAssistant,
    load_int: ConfigEntry,
) -> None:
    """Test the Coolmaster climate friendly name."""
    assert hass.states.get("climate.l1_100").attributes[ATTR_FRIENDLY_NAME] == "L1.100"
    assert hass.states.get("climate.l1_101").attributes[ATTR_FRIENDLY_NAME] == "L1.101"


async def test_climate_supported_features(
    hass: HomeAssistant,
    load_int: ConfigEntry,
) -> None:
    """Test the Coolmaster climate supported features."""
    assert hass.states.get("climate.l1_100").attributes[ATTR_SUPPORTED_FEATURES] == (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )
    assert hass.states.get("climate.l1_101").attributes[ATTR_SUPPORTED_FEATURES] == (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.SWING_MODE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )


async def test_climate_temperature(
    hass: HomeAssistant,
    load_int: ConfigEntry,
) -> None:
    """Test the Coolmaster climate current temperature."""
    assert hass.states.get("climate.l1_100").attributes[ATTR_CURRENT_TEMPERATURE] == 25
    assert hass.states.get("climate.l1_101").attributes[ATTR_CURRENT_TEMPERATURE] == 10


async def test_climate_thermostat(
    hass: HomeAssistant,
    load_int: ConfigEntry,
) -> None:
    """Test the Coolmaster climate thermostat."""
    assert hass.states.get("climate.l1_100").attributes[ATTR_TEMPERATURE] == 20
    assert hass.states.get("climate.l1_101").attributes[ATTR_TEMPERATURE] == 20


async def test_climate_hvac_modes(
    hass: HomeAssistant,
    load_int: ConfigEntry,
) -> None:
    """Test the Coolmaster climate hvac modes."""
    assert hass.states.get("climate.l1_100").attributes[ATTR_HVAC_MODES] == [
        HVACMode.OFF,
        HVACMode.COOL,
        HVACMode.HEAT,
    ]
    assert (
        hass.states.get("climate.l1_101").attributes[ATTR_HVAC_MODES]
        == hass.states.get("climate.l1_100").attributes[ATTR_HVAC_MODES]
    )


async def test_climate_fan_mode(
    hass: HomeAssistant,
    load_int: ConfigEntry,
) -> None:
    """Test the Coolmaster climate fan mode."""
    assert hass.states.get("climate.l1_100").attributes[ATTR_FAN_MODE] == FAN_LOW
    assert hass.states.get("climate.l1_101").attributes[ATTR_FAN_MODE] == FAN_HIGH


async def test_climate_fan_modes(
    hass: HomeAssistant,
    load_int: ConfigEntry,
) -> None:
    """Test the Coolmaster climate fan modes."""
    assert hass.states.get("climate.l1_100").attributes[ATTR_FAN_MODES] == FAN_MODES
    assert (
        hass.states.get("climate.l1_101").attributes[ATTR_FAN_MODES]
        == hass.states.get("climate.l1_100").attributes[ATTR_FAN_MODES]
    )


async def test_climate_swing_mode(
    hass: HomeAssistant,
    load_int: ConfigEntry,
) -> None:
    """Test the Coolmaster climate swing mode."""
    assert ATTR_SWING_MODE not in hass.states.get("climate.l1_100").attributes
    assert hass.states.get("climate.l1_101").attributes[ATTR_SWING_MODE] == "horizontal"


async def test_climate_swing_modes(
    hass: HomeAssistant,
    load_int: ConfigEntry,
) -> None:
    """Test the Coolmaster climate swing modes."""
    assert ATTR_SWING_MODES not in hass.states.get("climate.l1_100").attributes
    assert hass.states.get("climate.l1_101").attributes[ATTR_SWING_MODES] == SWING_MODES


async def test_set_temperature(
    hass: HomeAssistant,
    load_int: ConfigEntry,
) -> None:
    """Test the Coolmaster climate set temperature."""
    assert hass.states.get("climate.l1_100").attributes[ATTR_TEMPERATURE] == 20
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: "climate.l1_100",
            ATTR_TEMPERATURE: 30,
        },
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get("climate.l1_100").attributes[ATTR_TEMPERATURE] == 30


async def test_set_fan_mode(
    hass: HomeAssistant,
    load_int: ConfigEntry,
) -> None:
    """Test the Coolmaster climate set fan mode."""
    assert hass.states.get("climate.l1_100").attributes[ATTR_FAN_MODE] == FAN_LOW
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {
            ATTR_ENTITY_ID: "climate.l1_100",
            ATTR_FAN_MODE: FAN_HIGH,
        },
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get("climate.l1_100").attributes[ATTR_FAN_MODE] == FAN_HIGH


async def test_set_swing_mode(
    hass: HomeAssistant,
    load_int: ConfigEntry,
) -> None:
    """Test the Coolmaster climate set swing mode."""
    assert hass.states.get("climate.l1_101").attributes[ATTR_SWING_MODE] == "horizontal"
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_SWING_MODE,
        {
            ATTR_ENTITY_ID: "climate.l1_101",
            ATTR_SWING_MODE: "vertical",
        },
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get("climate.l1_101").attributes[ATTR_SWING_MODE] == "vertical"


async def test_set_swing_mode_error(
    hass: HomeAssistant,
    load_int: ConfigEntry,
) -> None:
    """Test the Coolmaster climate set swing mode with error."""
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_SWING_MODE,
            {
                ATTR_ENTITY_ID: "climate.l1_101",
                ATTR_SWING_MODE: "",
            },
            blocking=True,
        )


async def test_set_hvac_mode(
    hass: HomeAssistant,
    load_int: ConfigEntry,
) -> None:
    """Test the Coolmaster climate set hvac mode."""
    assert hass.states.get("climate.l1_100").state == HVACMode.OFF
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {
            ATTR_ENTITY_ID: "climate.l1_100",
            ATTR_HVAC_MODE: HVACMode.HEAT,
        },
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get("climate.l1_100").state == HVACMode.HEAT


async def test_set_hvac_mode_off(
    hass: HomeAssistant,
    load_int: ConfigEntry,
) -> None:
    """Test the Coolmaster climate set hvac mode to off."""
    assert hass.states.get("climate.l1_101").state == HVACMode.HEAT
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {
            ATTR_ENTITY_ID: "climate.l1_101",
            ATTR_HVAC_MODE: HVACMode.OFF,
        },
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get("climate.l1_101").state == HVACMode.OFF


async def test_turn_on(
    hass: HomeAssistant,
    load_int: ConfigEntry,
) -> None:
    """Test the Coolmaster climate turn on."""
    assert hass.states.get("climate.l1_100").state == HVACMode.OFF
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "climate.l1_100",
        },
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get("climate.l1_100").state == HVACMode.COOL


async def test_turn_off(
    hass: HomeAssistant,
    load_int: ConfigEntry,
) -> None:
    """Test the Coolmaster climate turn off."""
    assert hass.states.get("climate.l1_101").state == HVACMode.HEAT
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_TURN_OFF,
        {
            ATTR_ENTITY_ID: "climate.l1_101",
        },
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get("climate.l1_101").state == HVACMode.OFF
