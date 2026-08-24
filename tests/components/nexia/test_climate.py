"""Tests for the nexia climate platform."""

from nexia.home import NexiaHome

from homeassistant.components.climate import HVACMode
from homeassistant.core import HomeAssistant

from .conftest import setup_integration


async def test_climate_zones(hass: HomeAssistant, patch_nexia_home: NexiaHome) -> None:
    """Test creation climate zones."""

    await setup_integration(hass, patch_nexia_home)

    state = hass.states.get("climate.nick_office_nick_office")
    assert state is not None
    assert state.state == HVACMode.HEAT_COOL
    expected_attributes = {
        "attribution": "Data provided by Trane Technologies",
        "current_humidity": 52.0,
        "current_temperature": 22.8,
        "dehumidify_setpoint": 45.0,
        "fan_mode": "Auto",
        "fan_modes": ["Auto", "On", "Circulate"],
        "friendly_name": "Nick Office",
        "humidity": 45.0,
        "hvac_action": "cooling",
        "hvac_modes": ["off", "auto", "heat_cool", "heat", "cool"],
        "max_humidity": 65.0,
        "max_temp": 37.2,
        "min_humidity": 35.0,
        "min_temp": 12.8,
        "preset_mode": "None",
        "preset_modes": ["None", "Home", "Away", "Sleep"],
        "supported_features": 415,
        "target_temp_high": 26.1,
        "target_temp_low": 17.2,
        "target_temp_step": 1.0,
        "temperature": None,
    }
    # Only test for a subset of attributes in case
    # HA changes the implementation and a new one appears
    for key, value in expected_attributes.items():
        assert state.attributes[key] == value, f"key = {key}"

    state = hass.states.get("climate.kitchen_kitchen")
    assert state is not None
    assert state.state == HVACMode.HEAT_COOL

    expected_attributes = {
        "attribution": "Data provided by Trane Technologies",
        "current_humidity": 36.0,
        "current_temperature": 25.0,
        "dehumidify_setpoint": 50.0,
        "fan_mode": "Auto",
        "fan_modes": ["Auto", "On", "Circulate"],
        "friendly_name": "Kitchen",
        "humidity": 50.0,
        "hvac_action": "idle",
        "hvac_modes": ["off", "auto", "heat_cool", "heat", "cool"],
        "max_humidity": 65.0,
        "max_temp": 37.2,
        "min_humidity": 35.0,
        "min_temp": 12.8,
        "preset_mode": "None",
        "preset_modes": ["None", "Home", "Away", "Sleep"],
        "supported_features": 415,
        "target_temp_high": 26.1,
        "target_temp_low": 17.2,
        "target_temp_step": 1.0,
        "temperature": None,
    }

    # Only test for a subset of attributes in case
    # HA changes the implementation and a new one appears
    for key, value in expected_attributes.items():
        assert state.attributes[key] == value, f"key = {key}"
