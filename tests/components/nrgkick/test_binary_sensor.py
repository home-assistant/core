"""Tests for the NRGkick binary sensor platform."""

from unittest.mock import patch

import pytest

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.nrgkick.const import STATUS_CHARGING
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant


@pytest.fixture
def mock_values_data_binary_sensor():
    """Mock values data for binary sensor tests."""
    return {
        "general": {
            "status": STATUS_CHARGING,  # Should result in Charging = ON
            "charge_permitted": True,  # Should result in Charge Permitted = ON
        }
    }


async def test_binary_sensors(
    hass: HomeAssistant,
    mock_config_entry,
    mock_nrgkick_api,
    mock_info_data,
    mock_control_data,
    mock_values_data_binary_sensor,
) -> None:
    """Test binary sensors."""
    mock_config_entry.add_to_hass(hass)

    # Setup mock data
    mock_nrgkick_api.get_info.return_value = mock_info_data
    mock_nrgkick_api.get_control.return_value = mock_control_data
    mock_nrgkick_api.get_values.return_value = mock_values_data_binary_sensor

    # Setup entry
    with (
        patch(
            "homeassistant.components.nrgkick.NRGkickAPI", return_value=mock_nrgkick_api
        ),
        patch("homeassistant.components.nrgkick.async_get_clientsession"),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Check entities

    # 1. Charging
    state = hass.states.get("binary_sensor.nrgkick_test_charging")
    assert state
    assert state.state == STATE_ON
    assert state.attributes["device_class"] == BinarySensorDeviceClass.BATTERY_CHARGING

    # 2. Charge Permitted
    state = hass.states.get("binary_sensor.nrgkick_test_charge_permitted")
    assert state
    assert state.state == STATE_ON
    assert state.attributes["device_class"] == BinarySensorDeviceClass.POWER

    # 3. Charge Pause (from control data)
    # mock_control_data has "charge_pause": 0 -> False -> OFF
    state = hass.states.get("binary_sensor.nrgkick_test_charge_pause")
    assert state
    assert state.state == STATE_OFF

    # Test state change - use new dict values to ensure coordinator detects change
    # (required because always_update=False compares data dicts)
    mock_nrgkick_api.get_values.return_value = {
        "general": {
            "status": 0,  # Not charging
            "charge_permitted": False,
        }
    }
    mock_nrgkick_api.get_control.return_value = {
        "current_set": 16.0,
        "charge_pause": 1,  # Paused -> True -> ON
        "energy_limit": 0,
        "phase_count": 3,
    }

    # Trigger update
    coordinator = mock_config_entry.runtime_data
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.nrgkick_test_charging")
    assert state
    assert state.state == STATE_OFF

    state = hass.states.get("binary_sensor.nrgkick_test_charge_permitted")
    assert state
    assert state.state == STATE_OFF

    state = hass.states.get("binary_sensor.nrgkick_test_charge_pause")
    assert state
    assert state.state == STATE_ON
