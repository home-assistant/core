"""The sensor tests for the tado platform."""

from .util import async_init_integration


async def test_water_heater_create_sensors(hass):
    """Test creation of water heater."""

    await async_init_integration(hass)

    state = hass.states.get("water_heater.water_heater")
    assert state.state == "auto"

    expected_attributes = {
        "current_temperature": None,
        "friendly_name": "Water Heater",
        "max_temp": 31.0,
        "min_temp": 16.0,
        "operation_list": ["auto", "heat", "off"],
        "operation_mode": "auto",
        "supported_features": 3,
        "target_temp_high": None,
        "target_temp_low": None,
        "temperature": 65.0,
    }
    # Only test for a subset of attributes in case
    # HA changes the implementation and a new one appears
    assert all(item in state.attributes.items() for item in expected_attributes.items())

    state = hass.states.get("water_heater.second_water_heater")
    assert state.state == "heat"

    expected_attributes = {
        "current_temperature": None,
        "friendly_name": "Second Water Heater",
        "max_temp": 31.0,
        "min_temp": 16.0,
        "operation_list": ["auto", "heat", "off"],
        "operation_mode": "heat",
        "supported_features": 3,
        "target_temp_high": None,
        "target_temp_low": None,
        "temperature": 30.0,
    }
    # Only test for a subset of attributes in case
    # HA changes the implementation and a new one appears
    assert all(item in state.attributes.items() for item in expected_attributes.items())
