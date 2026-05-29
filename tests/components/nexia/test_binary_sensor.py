"""Tests for the nexia binary_sensor platform."""

from nexia.home import NexiaHome

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from .conftest import setup_integration


async def test_create_binary_sensors(
    hass: HomeAssistant, mock_nexia_home: NexiaHome
) -> None:
    """Test creation of binary sensors."""

    await setup_integration(hass, mock_nexia_home)

    state = hass.states.get("binary_sensor.master_suite_blower_active")
    assert state is not None
    assert state.state == STATE_ON
    expected_attributes = {
        "attribution": "Data provided by Trane Technologies",
        "friendly_name": "Master Suite Blower active",
    }
    # Only test for a subset of attributes in case
    # HA changes the implementation and a new one appears
    assert all(
        state.attributes[key] == value for key, value in expected_attributes.items()
    )

    state = hass.states.get("binary_sensor.downstairs_east_wing_blower_active")
    assert state is not None
    assert state.state == STATE_OFF
    expected_attributes = {
        "attribution": "Data provided by Trane Technologies",
        "friendly_name": "Downstairs East Wing Blower active",
    }
    # Only test for a subset of attributes in case
    # HA changes the implementation and a new one appears
    assert all(
        state.attributes[key] == value for key, value in expected_attributes.items()
    )
