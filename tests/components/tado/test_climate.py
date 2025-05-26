"""The sensor tests for the tado platform."""

from unittest.mock import patch

from PyTado.interface.api.my_tado import TadoZone
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACMode,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant

from .util import async_init_integration


async def test_air_con(hass: HomeAssistant) -> None:
    """Test creation of aircon climate."""

    await async_init_integration(hass)

    state = hass.states.get("climate.air_conditioning")
    assert state.state == "cool"

    expected_attributes = {
        "current_humidity": 60.9,
        "current_temperature": 24.8,
        "fan_mode": "auto",
        "fan_modes": ["auto", "high", "medium", "low"],
        "friendly_name": "Air Conditioning",
        "hvac_action": "cooling",
        "hvac_modes": ["off", "auto", "heat", "cool", "heat_cool", "dry", "fan_only"],
        "max_temp": 31.0,
        "min_temp": 16.0,
        "preset_mode": "auto",
        "preset_modes": ["away", "home", "auto"],
        "supported_features": 409,
        "target_temp_step": 1,
        "temperature": 17.8,
    }
    # Only test for a subset of attributes in case
    # HA changes the implementation and a new one appears
    assert all(item in state.attributes.items() for item in expected_attributes.items())


async def test_heater(hass: HomeAssistant) -> None:
    """Test creation of heater climate."""

    await async_init_integration(hass)

    state = hass.states.get("climate.baseboard_heater")
    assert state.state == "heat"

    expected_attributes = {
        "current_humidity": 45.2,
        "current_temperature": 20.6,
        "friendly_name": "Baseboard Heater",
        "hvac_action": "idle",
        "hvac_modes": ["off", "auto", "heat"],
        "max_temp": 31.0,
        "min_temp": 16.0,
        "preset_mode": "auto",
        "preset_modes": ["away", "home", "auto"],
        "supported_features": 401,
        "target_temp_step": 1,
        "temperature": 20.5,
    }
    # Only test for a subset of attributes in case
    # HA changes the implementation and a new one appears
    assert all(item in state.attributes.items() for item in expected_attributes.items())


async def test_smartac_with_swing(hass: HomeAssistant) -> None:
    """Test creation of smart ac with swing climate."""

    await async_init_integration(hass)

    state = hass.states.get("climate.air_conditioning_with_swing")
    assert state.state == "auto"

    expected_attributes = {
        "current_humidity": 42.3,
        "current_temperature": 20.9,
        "fan_mode": "auto",
        "fan_modes": ["auto", "high", "medium", "low"],
        "friendly_name": "Air Conditioning with swing",
        "hvac_action": "heating",
        "hvac_modes": ["off", "auto", "heat", "cool", "heat_cool", "dry", "fan_only"],
        "max_temp": 30.0,
        "min_temp": 16.0,
        "preset_mode": "auto",
        "preset_modes": ["away", "home", "auto"],
        "swing_modes": ["on", "off"],
        "supported_features": 441,
        "target_temp_step": 1.0,
        "temperature": 20.0,
    }
    # Only test for a subset of attributes in case
    # HA changes the implementation and a new one appears
    assert all(item in state.attributes.items() for item in expected_attributes.items())


async def test_smartac_with_fanlevel_vertical_and_horizontal_swing(
    hass: HomeAssistant,
) -> None:
    """Test creation of smart ac with swing climate."""

    await async_init_integration(hass)

    state = hass.states.get("climate.air_conditioning_with_fanlevel")
    assert state.state == "heat"

    expected_attributes = {
        "current_humidity": 70.9,
        "current_temperature": 24.3,
        "fan_mode": "high",
        "fan_modes": ["high", "medium", "auto", "low"],
        "friendly_name": "Air Conditioning with fanlevel",
        "hvac_action": "heating",
        "hvac_modes": ["off", "auto", "heat", "cool", "heat_cool", "dry", "fan_only"],
        "max_temp": 31.0,
        "min_temp": 16.0,
        "preset_mode": "auto",
        "preset_modes": ["away", "home", "auto"],
        "swing_modes": ["vertical", "horizontal", "both", "off"],
        "supported_features": 441,
        "target_temp_step": 1.0,
        "temperature": 25.0,
    }
    # Only test for a subset of attributes in case
    # HA changes the implementation and a new one appears
    assert all(item in state.attributes.items() for item in expected_attributes.items())


async def test_heater_set_temperature(
    hass: HomeAssistant, snapshot: SnapshotAssertion
) -> None:
    """Test the set temperature of the heater."""

    await async_init_integration(hass)

    with (
        patch(
            "homeassistant.components.tado.PyTado.interface.api.Tado.set_zone_overlay"
        ) as mock_set_state,
        patch(
            "homeassistant.components.tado.PyTado.interface.api.Tado.get_zone_state",
            return_value={"setting": {"temperature": {"celsius": 22.0}}},
        ),
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: "climate.baseboard_heater", ATTR_TEMPERATURE: 22.0},
            blocking=True,
        )

    mock_set_state.assert_called_once()
    snapshot.assert_match(mock_set_state.call_args)


@pytest.mark.parametrize(
    ("hvac_mode", "set_hvac_mode"),
    [
        (HVACMode.HEAT, "HEAT"),
        (HVACMode.DRY, "DRY"),
        (HVACMode.FAN_ONLY, "FAN"),
        (HVACMode.COOL, "COOL"),
        (HVACMode.OFF, "OFF"),
    ],
)
async def test_aircon_set_hvac_mode(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    hvac_mode: HVACMode,
    set_hvac_mode: str,
) -> None:
    """Test the set hvac mode of the air conditioning."""

    await async_init_integration(hass)

    with (
        patch(
            "homeassistant.components.tado.__init__.PyTado.interface.api.Tado.set_zone_overlay"
        ) as mock_set_state,
        patch(
            "homeassistant.components.tado.__init__.PyTado.interface.api.Tado.get_zone_state",
            return_value=TadoZone(
                zone_id=1,
                current_temp=18.7,
                connection=None,
                current_temp_timestamp="2025-01-02T12:51:52.802Z",
                current_humidity=45.1,
                current_humidity_timestamp="2025-01-02T12:51:52.802Z",
                is_away=False,
                current_hvac_action="IDLE",
                current_fan_speed=None,
                current_fan_level=None,
                current_hvac_mode=set_hvac_mode,
                current_swing_mode="OFF",
                current_vertical_swing_mode="OFF",
                current_horizontal_swing_mode="OFF",
                target_temp=16.0,
                available=True,
                power="ON",
                link="ONLINE",
                ac_power_timestamp=None,
                heating_power_timestamp="2025-01-02T13:01:11.758Z",
                ac_power=None,
                heating_power=None,
                heating_power_percentage=0.0,
                tado_mode="HOME",
                overlay_termination_type="MANUAL",
                overlay_termination_timestamp=None,
                default_overlay_termination_type="MANUAL",
                default_overlay_termination_duration=None,
                preparation=False,
                open_window=False,
                open_window_detected=False,
                open_window_attr={},
                precision=0.1,
            ),
        ),
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: "climate.air_conditioning", ATTR_HVAC_MODE: hvac_mode},
            blocking=True,
        )

    mock_set_state.assert_called_once()
    snapshot.assert_match(mock_set_state.call_args)
