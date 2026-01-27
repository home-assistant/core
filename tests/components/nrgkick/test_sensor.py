"""Tests for the NRGkick sensor platform."""

from datetime import datetime, timedelta
import json
from unittest.mock import patch

from nrgkick_api import ChargingStatus, ConnectorType, GridPhases
import pytest

from homeassistant.components.nrgkick.const import DOMAIN
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import (
    STATE_UNKNOWN,
    UnitOfPower,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from . import async_setup_integration

from tests.common import load_fixture


@pytest.fixture
def mock_values_data_sensor():
    """Mock values data for sensor tests."""
    return json.loads(load_fixture("values_sensor.json", DOMAIN))


async def test_sensor_entities(
    hass: HomeAssistant,
    mock_config_entry,
    mock_nrgkick_api,
    mock_info_data,
    mock_control_data,
    mock_values_data_sensor,
) -> None:
    """Test sensor entities."""

    # Make enum-like info fields numeric as well (these are mapped via tables).
    mock_info_data["connector"]["type"] = ConnectorType.TYPE2
    mock_info_data["grid"]["phases"] = GridPhases.L1_L2_L3

    # Setup mock data
    mock_nrgkick_api.get_info.return_value = mock_info_data
    mock_nrgkick_api.get_control.return_value = mock_control_data
    mock_nrgkick_api.get_values.return_value = mock_values_data_sensor

    # Setup entry
    now = datetime(2025, 1, 1, 0, 0, 0, tzinfo=dt_util.UTC)
    with patch("homeassistant.components.nrgkick.sensor.utcnow", return_value=now):
        await async_setup_integration(hass, mock_config_entry)

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

    # Test charging rate sensor (range added per hour)
    state = get_state_by_key("charging_rate")
    assert state is not None
    assert float(state.state) == 11.0
    assert state.attributes["unit_of_measurement"] == UnitOfSpeed.KILOMETERS_PER_HOUR

    # Test derived timestamp sensor (invariant to polling cadence)
    state = get_state_by_key("vehicle_connected_since")
    assert state is not None
    assert state.attributes["device_class"] == SensorDeviceClass.TIMESTAMP
    assert dt_util.parse_datetime(state.state) == now - timedelta(seconds=100)

    # Test mapped sensors (API returns numeric codes, mapped to translation keys)
    mapped_sensors = {
        "status": "charging",
        "rcd_trigger": "no_fault",
        "warning_code": "no_warning",
        "error_code": "no_error",
        "connector_type": "type2",
    }
    for key, expected in mapped_sensors.items():
        state = get_state_by_key(key)
        assert state is not None, f"{key}: state not found"
        assert state.state == expected, f"{key}: expected {expected}, got {state.state}"

    # Test numeric sensors
    numeric_sensors = {
        "rated_current": 32.0,
        "charging_current": 16.0,
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

    state = get_state_by_key("charging_current")
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

    mock_info_data["connector"]["type"] = ConnectorType.UNKNOWN
    mock_info_data["grid"]["phases"] = GridPhases.UNKNOWN
    mock_values_data_sensor["general"]["status"] = ChargingStatus.UNKNOWN

    mock_nrgkick_api.get_info.return_value = mock_info_data
    mock_nrgkick_api.get_control.return_value = mock_control_data
    mock_nrgkick_api.get_values.return_value = mock_values_data_sensor

    await async_setup_integration(hass, mock_config_entry)

    entity_registry = er.async_get(hass)

    def get_state_by_key(key):
        unique_id = f"TEST123456_{key}"
        entity_id = entity_registry.async_get_entity_id("sensor", "nrgkick", unique_id)
        return hass.states.get(entity_id) if entity_id else None

    for key in ("connector_type", "status"):
        state = get_state_by_key(key)
        assert state is not None
        assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize(
    ("model_type", "expect_optional_entities"),
    [
        ("NRGkick Gen2", False),
        ("NRGkick Gen2 SIM", True),
    ],
)
async def test_cellular_and_gps_entities_are_gated_by_model_type(
    hass: HomeAssistant,
    mock_config_entry,
    mock_nrgkick_api,
    mock_info_data,
    mock_control_data,
    mock_values_data_sensor,
    model_type: str,
    expect_optional_entities: bool,
) -> None:
    """Test that cellular/GPS entities are only created for SIM-capable models (GPS to be added later)."""

    mock_info_data["general"]["model_type"] = model_type

    # Include example payload sections. Even if values are missing/None, the
    # sensors should still be created when the model supports the modules.
    mock_info_data["cellular"] = {"mode": None, "rssi": None, "operator": None}

    mock_nrgkick_api.get_info.return_value = mock_info_data
    mock_nrgkick_api.get_control.return_value = mock_control_data
    mock_nrgkick_api.get_values.return_value = mock_values_data_sensor

    await async_setup_integration(hass, mock_config_entry)

    entity_registry = er.async_get(hass)
    optional_keys = (
        "cellular_mode",
        "cellular_rssi",
        "cellular_operator",
    )
    for key in optional_keys:
        unique_id = f"TEST123456_{key}"
        entity_id = entity_registry.async_get_entity_id("sensor", "nrgkick", unique_id)
        if expect_optional_entities:
            assert entity_id is not None, f"{model_type}: expected {key} to be created"
        else:
            assert entity_id is None, (
                f"{model_type}: did not expect {key} to be created"
            )
