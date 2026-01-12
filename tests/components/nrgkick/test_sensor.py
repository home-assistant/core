"""Tests for the NRGkick sensor platform."""

from unittest.mock import patch

from nrgkick_api import (
    ChargingStatus,
    ConnectorType,
    ErrorCode,
    GridPhases,
    RcdTriggerStatus,
    RelayState,
    WarningCode,
)
import pytest

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import STATE_UNKNOWN, UnitOfPower, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


@pytest.fixture
def mock_values_data_sensor():
    """Mock values data for sensor tests."""
    return {
        "powerflow": {
            "total_active_power": 11000,
            "l1": {
                "voltage": 230.0,
                "current": 16.0,
                "active_power": 3680,
                "reactive_power": 0,
                "apparent_power": 3680,
                "power_factor": 100,
            },
            "l2": {
                "voltage": 230.0,
                "current": 16.0,
                "active_power": 3680,
                "reactive_power": 0,
                "apparent_power": 3680,
                "power_factor": 100,
            },
            "l3": {
                "voltage": 230.0,
                "current": 16.0,
                "active_power": 3680,
                "reactive_power": 0,
                "apparent_power": 3680,
                "power_factor": 100,
            },
            "charging_voltage": 230.0,
            "charging_current": 16.0,
            "grid_frequency": 50.0,
            "peak_power": 11000,
            "total_reactive_power": 0,
            "total_apparent_power": 11040,
            "total_power_factor": 100,
            "n": {"current": 0.0},
        },
        "general": {
            # Use numeric (IntEnum) values to exercise mapping tables.
            "status": ChargingStatus.CHARGING,
            "charging_rate": 11.0,
            "vehicle_connect_time": 100,
            "vehicle_charging_time": 50,
            "charge_count": 5,
            "charge_permitted": True,
            "relay_state": RelayState.N_L1_L2_L3,
            "rcd_trigger": RcdTriggerStatus.NO_FAULT,
            "warning_code": WarningCode.NO_WARNING,
            "error_code": ErrorCode.NO_ERROR,
        },
        "temperatures": {
            "housing": 35.0,
            "connector_l1": 28.0,
            "connector_l2": 29.0,
            "connector_l3": 28.5,
            "domestic_plug_1": 25.0,
            "domestic_plug_2": 25.0,
        },
        "energy": {
            "total_charged_energy": 100000,
            "charged_energy": 5000,
        },
    }


async def test_sensor_entities(
    hass: HomeAssistant,
    mock_config_entry,
    mock_nrgkick_api,
    mock_info_data,
    mock_control_data,
    mock_values_data_sensor,
) -> None:
    """Test sensor entities."""
    mock_config_entry.add_to_hass(hass)

    # Make enum-like info fields numeric as well (these are mapped via tables).
    mock_info_data["connector"]["type"] = ConnectorType.TYPE2
    mock_info_data["grid"]["phases"] = GridPhases.L1_L2_L3

    # Setup mock data
    mock_nrgkick_api.get_info.return_value = mock_info_data
    mock_nrgkick_api.get_control.return_value = mock_control_data
    mock_nrgkick_api.get_values.return_value = mock_values_data_sensor

    # Setup entry
    with (
        patch(
            "homeassistant.components.nrgkick.NRGkickAPI", return_value=mock_nrgkick_api
        ),
        patch("homeassistant.components.nrgkick.async_get_clientsession"),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Helper to get state by unique ID
    entity_registry = er.async_get(hass)

    def get_state_by_key(key):
        unique_id = f"TEST123456_{key}"
        entity_id = entity_registry.async_get_entity_id("sensor", "nrgkick", unique_id)
        return hass.states.get(entity_id) if entity_id else None

    # Test power sensor with attributes
    state = get_state_by_key("total_active_power")
    assert state is not None
    assert float(state.state) == 11000.0
    assert state.attributes["unit_of_measurement"] == UnitOfPower.WATT
    assert state.attributes["device_class"] == SensorDeviceClass.POWER

    # Test temperature sensor
    state = get_state_by_key("housing_temperature")
    assert state is not None
    assert float(state.state) == 35.0
    assert state.attributes["unit_of_measurement"] == UnitOfTemperature.CELSIUS

    # Test mapped sensors (API returns numeric codes, mapped to translation keys)
    mapped_sensors = {
        "status": "charging",
        "rcd_trigger": "no_fault",
        "warning_code": "no_warning",
        "error_code": "no_error",
        "relay_state": "n_l1_l2_l3",
        "connector_type": "type2",
        "grid_phases": "l1_l2_l3",
    }
    for key, expected in mapped_sensors.items():
        state = get_state_by_key(key)
        assert state is not None, f"{key}: state not found"
        assert state.state == expected, f"{key}: expected {expected}, got {state.state}"

    # Test numeric sensors
    numeric_sensors = {
        "rated_current": 32.0,
        "charging_current": 16.0,
        "current_set": 16.0,
    }
    for key, expected in numeric_sensors.items():
        state = get_state_by_key(key)
        assert state is not None, f"{key}: state not found"
        assert float(state.state) == expected, f"{key}: expected {expected}"

    # Defensive: if the API returns an unexpected type for a nested section,
    # the entity should fall back to unknown (native_value=None).
    coordinator = mock_config_entry.runtime_data
    assert coordinator is not None
    coordinator.data.values["powerflow"] = "not-a-dict"
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    state = get_state_by_key("l1_voltage")
    assert state is not None
    assert state.state == STATE_UNKNOWN


async def test_mapped_unknown_values_become_state_unknown(
    hass: HomeAssistant,
    mock_config_entry,
    mock_nrgkick_api,
    mock_info_data,
    mock_control_data,
    mock_values_data_sensor,
) -> None:
    """Test that enum-like UNKNOWN values map to HA's unknown state."""
    mock_config_entry.add_to_hass(hass)

    mock_info_data["connector"]["type"] = ConnectorType.UNKNOWN
    mock_info_data["grid"]["phases"] = GridPhases.UNKNOWN
    mock_values_data_sensor["general"]["status"] = ChargingStatus.UNKNOWN

    mock_nrgkick_api.get_info.return_value = mock_info_data
    mock_nrgkick_api.get_control.return_value = mock_control_data
    mock_nrgkick_api.get_values.return_value = mock_values_data_sensor

    with (
        patch(
            "homeassistant.components.nrgkick.NRGkickAPI", return_value=mock_nrgkick_api
        ),
        patch("homeassistant.components.nrgkick.async_get_clientsession"),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entity_registry = er.async_get(hass)

    def get_state_by_key(key):
        unique_id = f"TEST123456_{key}"
        entity_id = entity_registry.async_get_entity_id("sensor", "nrgkick", unique_id)
        return hass.states.get(entity_id) if entity_id else None

    for key in ("connector_type", "grid_phases", "status"):
        state = get_state_by_key(key)
        assert state is not None
        assert state.state == STATE_UNKNOWN
