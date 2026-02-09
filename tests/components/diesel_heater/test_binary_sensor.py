"""Tests for Diesel Heater binary_sensor platform."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock

# Import stubs first
from . import conftest  # noqa: F401

from custom_components.diesel_heater.binary_sensor import (
    VevorHeaterActiveSensor,
    VevorHeaterProblemSensor,
    VevorHeaterConnectedSensor,
    VevorAutoStartStopSensor,
    async_setup_entry,
)
from custom_components.diesel_heater.const import (
    RUNNING_MODE_TEMPERATURE,
    RUNNING_MODE_LEVEL,
)


def create_mock_coordinator(protocol_mode: int = 0) -> MagicMock:
    """Create a mock coordinator for binary_sensor testing."""
    coordinator = MagicMock()
    coordinator._address = "AA:BB:CC:DD:EE:FF"
    coordinator.address = "AA:BB:CC:DD:EE:FF"
    coordinator._heater_id = "EE:FF"
    coordinator.last_update_success = True
    coordinator.protocol_mode = protocol_mode
    coordinator.data = {
        "connected": True,
        "running_state": 1,
        "running_step": 3,
        "running_mode": RUNNING_MODE_TEMPERATURE,
        "error_code": 0,
        "auto_start_stop": False,
    }
    return coordinator


# ---------------------------------------------------------------------------
# Active sensor tests
# ---------------------------------------------------------------------------

class TestVevorHeaterActiveSensor:
    """Tests for Vevor heater active binary sensor."""

    def test_is_on_when_running(self):
        """Test is_on returns True when heater is running."""
        coordinator = create_mock_coordinator()
        coordinator.data["running_state"] = 1
        sensor = VevorHeaterActiveSensor(coordinator)

        assert sensor.is_on is True

    def test_is_on_when_off(self):
        """Test is_on returns False when heater is off."""
        coordinator = create_mock_coordinator()
        coordinator.data["running_state"] = 0
        sensor = VevorHeaterActiveSensor(coordinator)

        assert sensor.is_on is False

    def test_unique_id(self):
        """Test unique_id format."""
        coordinator = create_mock_coordinator()
        sensor = VevorHeaterActiveSensor(coordinator)

        assert "_active" in sensor.unique_id or "_running" in sensor.unique_id


# ---------------------------------------------------------------------------
# Problem sensor tests
# ---------------------------------------------------------------------------

class TestVevorHeaterProblemSensor:
    """Tests for Vevor heater problem binary sensor."""

    def test_is_on_when_error(self):
        """Test is_on returns True when there's an error."""
        coordinator = create_mock_coordinator()
        coordinator.data["error_code"] = 1  # Some error
        sensor = VevorHeaterProblemSensor(coordinator)

        assert sensor.is_on is True

    def test_is_on_when_no_error(self):
        """Test is_on returns False when no error."""
        coordinator = create_mock_coordinator()
        coordinator.data["error_code"] = 0  # No error
        sensor = VevorHeaterProblemSensor(coordinator)

        assert sensor.is_on is False

    def test_unique_id(self):
        """Test unique_id format."""
        coordinator = create_mock_coordinator()
        sensor = VevorHeaterProblemSensor(coordinator)

        assert "_problem" in sensor.unique_id or "_error" in sensor.unique_id


# ---------------------------------------------------------------------------
# Connected sensor tests
# ---------------------------------------------------------------------------

class TestVevorHeaterConnectedSensor:
    """Tests for Vevor heater connected binary sensor."""

    def test_is_on_when_connected(self):
        """Test is_on returns True when heater is connected."""
        coordinator = create_mock_coordinator()
        coordinator.data["connected"] = True
        sensor = VevorHeaterConnectedSensor(coordinator)

        assert sensor.is_on is True

    def test_is_on_when_disconnected(self):
        """Test is_on returns False when heater is disconnected."""
        coordinator = create_mock_coordinator()
        coordinator.data["connected"] = False
        sensor = VevorHeaterConnectedSensor(coordinator)

        assert sensor.is_on is False

    def test_unique_id(self):
        """Test unique_id format."""
        coordinator = create_mock_coordinator()
        sensor = VevorHeaterConnectedSensor(coordinator)

        assert "_connected" in sensor.unique_id


# ---------------------------------------------------------------------------
# Availability tests
# ---------------------------------------------------------------------------

class TestBinarySensorAvailability:
    """Tests for binary sensor availability."""

    def test_available_when_connected(self):
        """Test binary sensor is available when connected."""
        coordinator = create_mock_coordinator()
        coordinator.last_update_success = True
        sensor = VevorHeaterActiveSensor(coordinator)

        assert sensor.available is True

    def test_available_property_exists(self):
        """Test available property is accessible."""
        coordinator = create_mock_coordinator()
        sensor = VevorHeaterActiveSensor(coordinator)

        # Just verify property is accessible
        _ = sensor.available


# ---------------------------------------------------------------------------
# Async setup entry tests
# ---------------------------------------------------------------------------

class TestAsyncSetupEntry:
    """Tests for async_setup_entry."""

    @pytest.mark.asyncio
    async def test_async_setup_entry_creates_core_sensors(self):
        """Test async_setup_entry creates core binary sensors."""
        coordinator = create_mock_coordinator(protocol_mode=1)

        # Create mock entry with runtime_data
        entry = MagicMock()
        entry.runtime_data = coordinator

        # Create mock async_add_entities
        async_add_entities = MagicMock()

        # Create mock hass
        hass = MagicMock()

        await async_setup_entry(hass, entry, async_add_entities)

        # Verify async_add_entities was called
        async_add_entities.assert_called_once()
        call_args = async_add_entities.call_args[0][0]
        # Mode 1 creates only 3 core sensors (no AutoStartStop)
        assert len(call_args) == 3

    @pytest.mark.asyncio
    async def test_async_setup_entry_protocol_mode_0(self):
        """Test async_setup_entry with protocol mode 0 includes all."""
        coordinator = create_mock_coordinator(protocol_mode=0)

        entry = MagicMock()
        entry.runtime_data = coordinator
        async_add_entities = MagicMock()
        hass = MagicMock()

        await async_setup_entry(hass, entry, async_add_entities)

        async_add_entities.assert_called_once()
        call_args = async_add_entities.call_args[0][0]
        # Mode 0 creates all 4 sensors
        assert len(call_args) == 4

    @pytest.mark.asyncio
    async def test_async_setup_entry_protocol_mode_5(self):
        """Test async_setup_entry with protocol mode 5 (ABBA) includes AutoStartStop."""
        coordinator = create_mock_coordinator(protocol_mode=5)

        entry = MagicMock()
        entry.runtime_data = coordinator
        async_add_entities = MagicMock()
        hass = MagicMock()

        await async_setup_entry(hass, entry, async_add_entities)

        async_add_entities.assert_called_once()
        call_args = async_add_entities.call_args[0][0]
        # Mode 5 includes AutoStartStop (4 sensors)
        assert len(call_args) == 4


# ---------------------------------------------------------------------------
# Auto Start/Stop sensor tests
# ---------------------------------------------------------------------------

class TestVevorAutoStartStopSensor:
    """Tests for Vevor Auto Start/Stop binary sensor."""

    def test_is_on_when_enabled(self):
        """Test is_on returns True when auto_start_stop is enabled."""
        coordinator = create_mock_coordinator()
        coordinator.data["auto_start_stop"] = True
        sensor = VevorAutoStartStopSensor(coordinator)

        assert sensor.is_on is True

    def test_is_on_when_disabled(self):
        """Test is_on returns False when auto_start_stop is disabled."""
        coordinator = create_mock_coordinator()
        coordinator.data["auto_start_stop"] = False
        sensor = VevorAutoStartStopSensor(coordinator)

        assert sensor.is_on is False

    def test_is_on_returns_none_when_missing(self):
        """Test is_on returns None when auto_start_stop is not in data."""
        coordinator = create_mock_coordinator()
        del coordinator.data["auto_start_stop"]
        sensor = VevorAutoStartStopSensor(coordinator)

        assert sensor.is_on is None

    def test_unique_id(self):
        """Test unique_id format."""
        coordinator = create_mock_coordinator()
        sensor = VevorAutoStartStopSensor(coordinator)

        assert "_auto_start_stop" in sensor.unique_id

    def test_icon(self):
        """Test icon is set."""
        coordinator = create_mock_coordinator()
        sensor = VevorAutoStartStopSensor(coordinator)

        assert sensor._attr_icon == "mdi:thermostat-auto"

    def test_name(self):
        """Test name is set."""
        coordinator = create_mock_coordinator()
        sensor = VevorAutoStartStopSensor(coordinator)

        assert sensor._attr_name == "Auto Start/Stop"

    def test_device_info(self):
        """Test device_info is set correctly."""
        coordinator = create_mock_coordinator()
        sensor = VevorAutoStartStopSensor(coordinator)

        assert sensor._attr_device_info is not None
        assert "identifiers" in sensor._attr_device_info


class TestAutoStartStopAvailability:
    """Tests for Auto Start/Stop sensor availability."""

    def test_available_in_temp_mode(self):
        """Test sensor is available in temperature mode."""
        coordinator = create_mock_coordinator()
        coordinator.data["connected"] = True
        coordinator.data["running_mode"] = RUNNING_MODE_TEMPERATURE
        sensor = VevorAutoStartStopSensor(coordinator)

        assert sensor.available is True

    def test_not_available_in_level_mode(self):
        """Test sensor is not available in level mode."""
        coordinator = create_mock_coordinator()
        coordinator.data["connected"] = True
        coordinator.data["running_mode"] = RUNNING_MODE_LEVEL
        sensor = VevorAutoStartStopSensor(coordinator)

        assert sensor.available is False

    def test_not_available_when_not_connected(self):
        """Test sensor is not available when not connected."""
        coordinator = create_mock_coordinator()
        coordinator.data["connected"] = False
        coordinator.data["running_mode"] = RUNNING_MODE_TEMPERATURE
        sensor = VevorAutoStartStopSensor(coordinator)

        assert sensor.available is False


# ---------------------------------------------------------------------------
# Entity attribute tests
# ---------------------------------------------------------------------------

class TestBinarySensorAttributes:
    """Tests for binary sensor entity attributes."""

    def test_active_sensor_has_entity_name(self):
        """Test active sensor has_entity_name is True."""
        coordinator = create_mock_coordinator()
        sensor = VevorHeaterActiveSensor(coordinator)

        assert sensor._attr_has_entity_name is True

    def test_active_sensor_name(self):
        """Test active sensor name."""
        coordinator = create_mock_coordinator()
        sensor = VevorHeaterActiveSensor(coordinator)

        assert sensor._attr_name == "Active"

    def test_problem_sensor_name(self):
        """Test problem sensor name."""
        coordinator = create_mock_coordinator()
        sensor = VevorHeaterProblemSensor(coordinator)

        assert sensor._attr_name == "Problem"

    def test_connected_sensor_name(self):
        """Test connected sensor name."""
        coordinator = create_mock_coordinator()
        sensor = VevorHeaterConnectedSensor(coordinator)

        assert sensor._attr_name == "Connected"

    def test_active_sensor_device_class(self):
        """Test active sensor device class."""
        coordinator = create_mock_coordinator()
        sensor = VevorHeaterActiveSensor(coordinator)

        # Device class is mocked, just check it's set
        assert sensor._attr_device_class is not None

    def test_problem_sensor_device_class(self):
        """Test problem sensor device class."""
        coordinator = create_mock_coordinator()
        sensor = VevorHeaterProblemSensor(coordinator)

        assert sensor._attr_device_class is not None

    def test_connected_sensor_device_class(self):
        """Test connected sensor device class."""
        coordinator = create_mock_coordinator()
        sensor = VevorHeaterConnectedSensor(coordinator)

        assert sensor._attr_device_class is not None

    def test_active_sensor_entity_category(self):
        """Test active sensor is in DIAGNOSTIC category."""
        coordinator = create_mock_coordinator()
        sensor = VevorHeaterActiveSensor(coordinator)

        assert sensor._attr_entity_category is not None

    def test_problem_sensor_entity_category(self):
        """Test problem sensor is in DIAGNOSTIC category."""
        coordinator = create_mock_coordinator()
        sensor = VevorHeaterProblemSensor(coordinator)

        assert sensor._attr_entity_category is not None

    def test_connected_sensor_disabled_by_default(self):
        """Test connected sensor is disabled by default."""
        coordinator = create_mock_coordinator()
        sensor = VevorHeaterConnectedSensor(coordinator)

        assert sensor._attr_entity_registry_enabled_default is False

    def test_active_sensor_device_info(self):
        """Test active sensor device_info."""
        coordinator = create_mock_coordinator()
        sensor = VevorHeaterActiveSensor(coordinator)

        assert sensor._attr_device_info is not None
        assert "identifiers" in sensor._attr_device_info

    def test_problem_sensor_device_info(self):
        """Test problem sensor device_info."""
        coordinator = create_mock_coordinator()
        sensor = VevorHeaterProblemSensor(coordinator)

        assert sensor._attr_device_info is not None

    def test_connected_sensor_device_info(self):
        """Test connected sensor device_info."""
        coordinator = create_mock_coordinator()
        sensor = VevorHeaterConnectedSensor(coordinator)

        assert sensor._attr_device_info is not None


# ---------------------------------------------------------------------------
# _handle_coordinator_update tests
# ---------------------------------------------------------------------------

class TestHandleCoordinatorUpdate:
    """Tests for _handle_coordinator_update on all binary sensor entities."""

    def test_active_sensor_handle_coordinator_update(self):
        """Test ActiveSensor _handle_coordinator_update calls async_write_ha_state."""
        coordinator = create_mock_coordinator()
        sensor = VevorHeaterActiveSensor(coordinator)
        sensor.async_write_ha_state = MagicMock()

        sensor._handle_coordinator_update()

        sensor.async_write_ha_state.assert_called_once()

    def test_problem_sensor_handle_coordinator_update(self):
        """Test ProblemSensor _handle_coordinator_update calls async_write_ha_state."""
        coordinator = create_mock_coordinator()
        sensor = VevorHeaterProblemSensor(coordinator)
        sensor.async_write_ha_state = MagicMock()

        sensor._handle_coordinator_update()

        sensor.async_write_ha_state.assert_called_once()

    def test_connected_sensor_handle_coordinator_update(self):
        """Test ConnectedSensor _handle_coordinator_update calls async_write_ha_state."""
        coordinator = create_mock_coordinator()
        sensor = VevorHeaterConnectedSensor(coordinator)
        sensor.async_write_ha_state = MagicMock()

        sensor._handle_coordinator_update()

        sensor.async_write_ha_state.assert_called_once()

    def test_auto_start_stop_sensor_handle_coordinator_update(self):
        """Test AutoStartStopSensor _handle_coordinator_update calls async_write_ha_state."""
        coordinator = create_mock_coordinator()
        sensor = VevorAutoStartStopSensor(coordinator)
        sensor.async_write_ha_state = MagicMock()

        sensor._handle_coordinator_update()

        sensor.async_write_ha_state.assert_called_once()
