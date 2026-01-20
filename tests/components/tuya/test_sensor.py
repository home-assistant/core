"""Test Tuya sensor platform."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion
from tuya_sharing import CustomerDevice, Manager

from homeassistant.components.sensor import SensorStateClass
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import MockDeviceListener, check_selective_state_update, initialize_entry

from tests.common import MockConfigEntry, snapshot_platform


@patch("homeassistant.components.tuya.PLATFORMS", [Platform.SENSOR])
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_platform_setup_and_discovery(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_devices: list[CustomerDevice],
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test platform setup and discovery."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_devices)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    "mock_device_code",
    ["mcs_8yhypbo7"],
)
@pytest.mark.parametrize(
    ("updates", "expected_state", "last_reported"),
    [
        # Update without dpcode - state should not change, last_reported stays at initial
        ({"doorcontact_state": True}, "62.0", "2024-01-01T00:00:00+00:00"),
        # Update with dpcode - state should change, last_reported advances
        ({"battery_percentage": 50}, "50.0", "2024-01-01T00:01:00+00:00"),
        # Update with multiple properties including dpcode - state should change
        (
            {"doorcontact_state": True, "battery_percentage": 50},
            "50.0",
            "2024-01-01T00:01:00+00:00",
        ),
    ],
)
@patch("homeassistant.components.tuya.PLATFORMS", [Platform.SENSOR])
@pytest.mark.freeze_time("2024-01-01")
async def test_selective_state_update(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    mock_listener: MockDeviceListener,
    freezer: FrozenDateTimeFactory,
    updates: dict[str, Any],
    expected_state: str,
    last_reported: str,
) -> None:
    """Test skip_update/last_reported."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)
    await check_selective_state_update(
        hass,
        mock_device,
        mock_listener,
        freezer,
        entity_id="sensor.boite_aux_lettres_arriere_battery",
        dpcode="battery_percentage",
        initial_state="62.0",
        updates=updates,
        expected_state=expected_state,
        last_reported=last_reported,
    )


@patch("homeassistant.components.tuya.PLATFORMS", [Platform.SENSOR])
@pytest.mark.parametrize("mock_device_code", ["cz_guitoc9iylae4axs"])
async def test_delta_report_sensor_initial_state(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Test delta report sensor initializes with zero value."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    # The entity_id is generated based on device name and dpcode translation key
    state = hass.states.get("sensor.ha_socket_delta_test_total_energy")

    assert state is not None
    # Delta sensors start from zero and accumulate values
    assert state.state == "0"
    assert state.attributes["state_class"] == SensorStateClass.TOTAL_INCREASING


@patch("homeassistant.components.tuya.PLATFORMS", [Platform.SENSOR])
@pytest.mark.parametrize("mock_device_code", ["cz_guitoc9iylae4axs"])
async def test_delta_report_sensor_accumulates_values(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    mock_listener: MockDeviceListener,
) -> None:
    """Test delta report sensor accumulates incremental values."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    # Initial state from fixture
    state = hass.states.get("sensor.ha_socket_delta_test_total_energy")
    assert state is not None
    initial_value = float(state.state)

    # Send delta update: device reports 200 (0.2 kWh after scaling)
    await mock_listener.async_send_device_update(
        hass,
        mock_device,
        {"add_ele": 200},
        {"add_ele": 1000},  # timestamp
    )

    state = hass.states.get("sensor.ha_socket_delta_test_total_energy")
    # Should accumulate: 0.1 + 0.2 = 0.3
    assert float(state.state) == pytest.approx(initial_value + 0.2)

    # Send another delta update: device reports 300 (0.3 kWh after scaling)
    await mock_listener.async_send_device_update(
        hass,
        mock_device,
        {"add_ele": 300},
        {"add_ele": 2000},  # new timestamp
    )

    state = hass.states.get("sensor.ha_socket_delta_test_total_energy")
    # Should accumulate: 0.3 + 0.3 = 0.6
    assert float(state.state) == pytest.approx(initial_value + 0.2 + 0.3)


@patch("homeassistant.components.tuya.PLATFORMS", [Platform.SENSOR])
@pytest.mark.parametrize("mock_device_code", ["cz_guitoc9iylae4axs"])
async def test_delta_report_sensor_skips_duplicate_timestamp(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    mock_listener: MockDeviceListener,
) -> None:
    """Test delta report sensor skips updates with duplicate timestamps."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    state = hass.states.get("sensor.ha_socket_delta_test_total_energy")
    initial_value = float(state.state)

    # First update
    await mock_listener.async_send_device_update(
        hass,
        mock_device,
        {"add_ele": 200},
        {"add_ele": 1000},
    )

    state = hass.states.get("sensor.ha_socket_delta_test_total_energy")
    value_after_first = float(state.state)
    assert value_after_first == pytest.approx(initial_value + 0.2)

    # Duplicate timestamp - should be ignored
    await mock_listener.async_send_device_update(
        hass,
        mock_device,
        {"add_ele": 500},
        {"add_ele": 1000},  # Same timestamp
    )

    state = hass.states.get("sensor.ha_socket_delta_test_total_energy")
    # Value should remain unchanged
    assert float(state.state) == pytest.approx(value_after_first)


@patch("homeassistant.components.tuya.PLATFORMS", [Platform.SENSOR])
@pytest.mark.parametrize("mock_device_code", ["cz_guitoc9iylae4axs"])
async def test_delta_report_sensor_handles_none_raw_value(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    mock_listener: MockDeviceListener,
) -> None:
    """Test delta report sensor handles None raw value gracefully."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    state = hass.states.get("sensor.ha_socket_delta_test_total_energy")
    assert state is not None
    initial_value = float(state.state)

    await mock_listener.async_send_device_update(
        hass,
        mock_device,
        {"add_ele": 200},
        {"add_ele": 1000},
    )

    state = hass.states.get("sensor.ha_socket_delta_test_total_energy")
    assert state is not None
    value_after_first = float(state.state)
    assert value_after_first == pytest.approx(initial_value + 0.2)

    mock_device.status["add_ele"] = None

    await mock_listener.async_send_device_update(
        hass,
        mock_device,
        {"add_ele": None},
        {"add_ele": 2000},
    )

    state = hass.states.get("sensor.ha_socket_delta_test_total_energy")
    assert state is not None
    assert float(state.state) == pytest.approx(value_after_first)


@patch("homeassistant.components.tuya.PLATFORMS", [Platform.SENSOR])
@pytest.mark.parametrize("mock_device_code", ["cz_guitoc9iylae4axs"])
async def test_delta_report_sensor_without_timestamp(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    mock_listener: MockDeviceListener,
) -> None:
    """Test delta report sensor handles updates without timestamps."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    state = hass.states.get("sensor.ha_socket_delta_test_total_energy")
    assert state is not None
    initial_value = float(state.state)

    await mock_listener.async_send_device_update(
        hass,
        mock_device,
        {"add_ele": 200},
        None,
    )

    state = hass.states.get("sensor.ha_socket_delta_test_total_energy")
    assert state is not None
    assert float(state.state) == pytest.approx(initial_value + 0.2)


@patch("homeassistant.components.tuya.PLATFORMS", [Platform.SENSOR])
@pytest.mark.parametrize("mock_device_code", ["cz_guitoc9iylae4axs"])
async def test_delta_report_update_skipped_for_unrelated_property(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    mock_listener: MockDeviceListener,
) -> None:
    """Test delta report sensor skips update when dpcode is not in updated properties."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    state = hass.states.get("sensor.ha_socket_delta_test_total_energy")
    assert state is not None
    initial_value = float(state.state)

    await mock_listener.async_send_device_update(
        hass,
        mock_device,
        {"switch_1": False},
        {"switch_1": 1000},
    )

    state = hass.states.get("sensor.ha_socket_delta_test_total_energy")
    assert state is not None
    assert float(state.state) == pytest.approx(initial_value)
