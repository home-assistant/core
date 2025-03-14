"""The lock tests for the august platform."""

from homeassistant.components.climate import HVACMode
from homeassistant.core import HomeAssistant

from .util import async_init_integration


async def test_climate_zones(hass: HomeAssistant) -> None:
    """Test creation climate zones."""

    await async_init_integration(hass)

    state = hass.states.get("climate.nick_office")
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
    assert all(
        state.attributes[key] == value for key, value in expected_attributes.items()
    )

    state = hass.states.get("climate.kitchen")
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
    assert all(
        state.attributes[key] == value for key, value in expected_attributes.items()
    )
