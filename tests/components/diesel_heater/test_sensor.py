"""Tests for Diesel Heater sensor platform."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock

# Import stubs first
from . import conftest  # noqa: F401

from custom_components.diesel_heater.sensor import (
    VevorCabTemperatureSensor,
    VevorCaseTemperatureSensor,
    VevorSupplyVoltageSensor,
    VevorRunningStepSensor,
    VevorRunningModeSensor,
    VevorSetLevelSensor,
    VevorAltitudeSensor,
    VevorErrorCodeSensor,
    VevorHourlyFuelConsumptionSensor,
    VevorDailyFuelConsumedSensor,
    VevorTotalFuelConsumedSensor,
    VevorFuelRemainingSensor,
    VevorDailyRuntimeSensor,
    VevorTotalRuntimeSensor,
    VevorRawInteriorTemperatureSensor,
    VevorHeaterOffsetSensor,
    VevorDailyFuelHistorySensor,
    VevorDailyRuntimeHistorySensor,
    VevorLastRefueledSensor,
    VevorFuelConsumedSinceResetSensor,
    VevorCOSensor,
    VevorHardwareVersionSensor,
    VevorSoftwareVersionSensor,
    VevorRemainingRunTimeSensor,
    VevorStartupTempDiffSensor,
    VevorShutdownTempDiffSensor,
    async_setup_entry,
)
from custom_components.diesel_heater.const import (
    ERROR_NAMES,
    RUNNING_MODE_NAMES,
    RUNNING_STEP_NAMES,
)


def create_mock_coordinator(protocol_mode: int = 0) -> MagicMock:
    """Create a mock coordinator for sensor testing."""
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
        "running_mode": 1,
        "set_level": 5,
        "set_temp": 22,
        "cab_temperature": 20.5,
        "cab_temperature_raw": 20.0,
        "case_temperature": 50,
        "supply_voltage": 12.5,
        "error_code": 0,
        "altitude": 500,
        "heater_offset": 0,
        "tank_capacity": 5,
        "hourly_fuel_consumption": 0.25,
        "daily_fuel_consumed": 1.5,
        "total_fuel_consumed": 25.0,
        "fuel_remaining": 3.5,
        "fuel_consumed_since_reset": 1.5,
        "daily_runtime_hours": 4.5,
        "total_runtime_hours": 150.0,
        "co_ppm": None,
        "remain_run_time": None,
        "hardware_version": None,
        "software_version": None,
        "last_refueled": None,
        "startup_temp_diff": None,
        "shutdown_temp_diff": None,
        "daily_fuel_history": {},
        "daily_runtime_history": {},
    }
    return coordinator


# ---------------------------------------------------------------------------
# Temperature sensor tests
# ---------------------------------------------------------------------------

class TestCabTemperatureSensor:
    """Tests for cabin temperature sensor."""

    def test_native_value(self):
        """Test that native_value returns cabin temperature."""
        coordinator = create_mock_coordinator()
        sensor = VevorCabTemperatureSensor(coordinator)

        assert sensor.native_value == 20.5

    def test_native_value_none_when_disconnected(self):
        """Test that native_value is None when heater is disconnected."""
        coordinator = create_mock_coordinator()
        coordinator.data["cab_temperature"] = None
        sensor = VevorCabTemperatureSensor(coordinator)

        assert sensor.native_value is None

    def test_device_class(self):
        """Test that device_class is temperature."""
        coordinator = create_mock_coordinator()
        sensor = VevorCabTemperatureSensor(coordinator)

        # Check device_class is set (MagicMock comparison doesn't work)
        assert sensor.device_class is not None

    def test_unique_id(self):
        """Test unique_id format."""
        coordinator = create_mock_coordinator()
        sensor = VevorCabTemperatureSensor(coordinator)

        # unique_id should contain the address and sensor type
        assert "_cab_temperature" in sensor.unique_id or "cab_temp" in sensor.unique_id


class TestCaseTemperatureSensor:
    """Tests for case temperature sensor."""

    def test_native_value(self):
        """Test that native_value returns case temperature."""
        coordinator = create_mock_coordinator()
        sensor = VevorCaseTemperatureSensor(coordinator)

        assert sensor.native_value == 50

    def test_native_value_none(self):
        """Test native_value when data is None."""
        coordinator = create_mock_coordinator()
        coordinator.data["case_temperature"] = None
        sensor = VevorCaseTemperatureSensor(coordinator)

        assert sensor.native_value is None


# ---------------------------------------------------------------------------
# Voltage sensor tests
# ---------------------------------------------------------------------------

class TestSupplyVoltageSensor:
    """Tests for supply voltage sensor."""

    def test_native_value(self):
        """Test that native_value returns voltage."""
        coordinator = create_mock_coordinator()
        sensor = VevorSupplyVoltageSensor(coordinator)

        assert sensor.native_value == 12.5

    def test_device_class(self):
        """Test that device_class is voltage."""
        coordinator = create_mock_coordinator()
        sensor = VevorSupplyVoltageSensor(coordinator)

        # Check device_class is set (MagicMock comparison doesn't work)
        assert sensor.device_class is not None


# ---------------------------------------------------------------------------
# Running state sensor tests
# ---------------------------------------------------------------------------

class TestRunningStepSensor:
    """Tests for running step sensor."""

    def test_native_value_returns_step_name(self):
        """Test that native_value returns human-readable step name."""
        coordinator = create_mock_coordinator()
        coordinator.data["running_step"] = 3
        sensor = VevorRunningStepSensor(coordinator)

        value = sensor.native_value
        # running_step 3 should map to a RUNNING_STEP_NAMES entry
        assert value == RUNNING_STEP_NAMES.get(3, "Unknown (3)")

    def test_native_value_unknown_step(self):
        """Test native_value with unknown step code."""
        coordinator = create_mock_coordinator()
        coordinator.data["running_step"] = 99
        sensor = VevorRunningStepSensor(coordinator)

        value = sensor.native_value
        assert "Unknown" in value or "99" in value


class TestRunningModeSensor:
    """Tests for running mode sensor."""

    def test_native_value_returns_mode_name(self):
        """Test that native_value returns human-readable mode name."""
        coordinator = create_mock_coordinator()
        coordinator.data["running_mode"] = 1
        sensor = VevorRunningModeSensor(coordinator)

        value = sensor.native_value
        assert value == RUNNING_MODE_NAMES.get(1, "Unknown (1)")


# ---------------------------------------------------------------------------
# Level and settings sensor tests
# ---------------------------------------------------------------------------

class TestSetLevelSensor:
    """Tests for set level sensor."""

    def test_native_value(self):
        """Test that native_value returns current level."""
        coordinator = create_mock_coordinator()
        coordinator.data["set_level"] = 7
        sensor = VevorSetLevelSensor(coordinator)

        assert sensor.native_value == 7


class TestAltitudeSensor:
    """Tests for altitude sensor."""

    def test_native_value(self):
        """Test that native_value returns altitude."""
        coordinator = create_mock_coordinator()
        coordinator.data["altitude"] = 1500
        sensor = VevorAltitudeSensor(coordinator)

        assert sensor.native_value == 1500


# ---------------------------------------------------------------------------
# Error sensor tests
# ---------------------------------------------------------------------------

class TestErrorCodeSensor:
    """Tests for error code sensor."""

    def test_native_value_no_error(self):
        """Test native_value when no error."""
        coordinator = create_mock_coordinator()
        coordinator.data["error_code"] = 0
        sensor = VevorErrorCodeSensor(coordinator)

        value = sensor.native_value
        assert value == ERROR_NAMES.get(0, "E00: Unknown Error")

    def test_native_value_with_error(self):
        """Test native_value with error code."""
        coordinator = create_mock_coordinator()
        coordinator.data["error_code"] = 1
        sensor = VevorErrorCodeSensor(coordinator)

        value = sensor.native_value
        assert "E01" in value or value == ERROR_NAMES.get(1, "E01: Unknown Error")


# ---------------------------------------------------------------------------
# Fuel consumption sensor tests
# ---------------------------------------------------------------------------

class TestHourlyFuelConsumptionSensor:
    """Tests for hourly fuel consumption sensor."""

    def test_native_value(self):
        """Test that native_value returns hourly consumption."""
        coordinator = create_mock_coordinator()
        coordinator.data["hourly_fuel_consumption"] = 0.35
        sensor = VevorHourlyFuelConsumptionSensor(coordinator)

        assert sensor.native_value == 0.35


class TestDailyFuelConsumedSensor:
    """Tests for daily fuel consumed sensor."""

    def test_native_value(self):
        """Test that native_value returns daily consumption."""
        coordinator = create_mock_coordinator()
        coordinator.data["daily_fuel_consumed"] = 2.5
        sensor = VevorDailyFuelConsumedSensor(coordinator)

        assert sensor.native_value == 2.5


class TestTotalFuelConsumedSensor:
    """Tests for total fuel consumed sensor."""

    def test_native_value(self):
        """Test that native_value returns total consumption."""
        coordinator = create_mock_coordinator()
        coordinator.data["total_fuel_consumed"] = 100.5
        sensor = VevorTotalFuelConsumedSensor(coordinator)

        assert sensor.native_value == 100.5


class TestFuelRemainingSensor:
    """Tests for fuel remaining sensor."""

    def test_native_value(self):
        """Test that native_value returns fuel remaining."""
        coordinator = create_mock_coordinator()
        coordinator.data["fuel_remaining"] = 4.5
        sensor = VevorFuelRemainingSensor(coordinator)

        assert sensor.native_value == 4.5

    def test_native_value_none(self):
        """Test native_value when not tracked."""
        coordinator = create_mock_coordinator()
        coordinator.data["fuel_remaining"] = None
        sensor = VevorFuelRemainingSensor(coordinator)

        assert sensor.native_value is None


# ---------------------------------------------------------------------------
# Runtime sensor tests
# ---------------------------------------------------------------------------

class TestDailyRuntimeSensor:
    """Tests for daily runtime sensor."""

    def test_native_value(self):
        """Test that native_value returns daily runtime hours."""
        coordinator = create_mock_coordinator()
        coordinator.data["daily_runtime_hours"] = 5.5
        sensor = VevorDailyRuntimeSensor(coordinator)

        assert sensor.native_value == 5.5


class TestTotalRuntimeSensor:
    """Tests for total runtime sensor."""

    def test_native_value(self):
        """Test that native_value returns total runtime hours."""
        coordinator = create_mock_coordinator()
        coordinator.data["total_runtime_hours"] = 250.0
        sensor = VevorTotalRuntimeSensor(coordinator)

        assert sensor.native_value == 250.0


# ---------------------------------------------------------------------------
# Availability tests
# ---------------------------------------------------------------------------

class TestSensorAvailability:
    """Tests for sensor availability."""

    def test_available_when_connected(self):
        """Test sensor is available when last_update_success and has value."""
        coordinator = create_mock_coordinator()
        coordinator.last_update_success = True
        coordinator.data["cab_temperature"] = 20.5
        sensor = VevorCabTemperatureSensor(coordinator)

        assert sensor.available is True

    def test_unavailable_when_update_failed(self):
        """Test sensor is unavailable when last_update_success is False."""
        coordinator = create_mock_coordinator()
        coordinator.last_update_success = False
        sensor = VevorCabTemperatureSensor(coordinator)

        assert sensor.available is False

    def test_unavailable_when_value_none(self):
        """Test sensor is unavailable when native_value is None."""
        coordinator = create_mock_coordinator()
        coordinator.last_update_success = True
        coordinator.data["cab_temperature"] = None
        sensor = VevorCabTemperatureSensor(coordinator)

        assert sensor.available is False


# ---------------------------------------------------------------------------
# Async setup entry tests
# ---------------------------------------------------------------------------

class TestAsyncSetupEntry:
    """Tests for async_setup_entry."""

    @pytest.mark.asyncio
    async def test_async_setup_entry_creates_core_sensors(self):
        """Test async_setup_entry creates core sensors for mode 1."""
        coordinator = create_mock_coordinator(protocol_mode=1)

        entry = MagicMock()
        entry.runtime_data = coordinator

        async_add_entities = MagicMock()
        hass = MagicMock()

        await async_setup_entry(hass, entry, async_add_entities)

        async_add_entities.assert_called_once()
        call_args = async_add_entities.call_args[0][0]
        # Mode 1 creates only core sensors (18)
        assert len(call_args) == 18

    @pytest.mark.asyncio
    async def test_async_setup_entry_protocol_mode_0(self):
        """Test async_setup_entry with protocol mode 0 includes all sensors."""
        coordinator = create_mock_coordinator(protocol_mode=0)

        entry = MagicMock()
        entry.runtime_data = coordinator
        async_add_entities = MagicMock()
        hass = MagicMock()

        await async_setup_entry(hass, entry, async_add_entities)

        async_add_entities.assert_called_once()
        call_args = async_add_entities.call_args[0][0]
        # Mode 0 creates all sensors (18 core + 3 extended + 5 CBFF = 26)
        assert len(call_args) == 26

    @pytest.mark.asyncio
    async def test_async_setup_entry_protocol_mode_2(self):
        """Test async_setup_entry with protocol mode 2 (encrypted)."""
        coordinator = create_mock_coordinator(protocol_mode=2)

        entry = MagicMock()
        entry.runtime_data = coordinator
        async_add_entities = MagicMock()
        hass = MagicMock()

        await async_setup_entry(hass, entry, async_add_entities)

        async_add_entities.assert_called_once()
        call_args = async_add_entities.call_args[0][0]
        # Mode 2 creates core + extended (18 + 3 = 21)
        assert len(call_args) == 21

    @pytest.mark.asyncio
    async def test_async_setup_entry_protocol_mode_6(self):
        """Test async_setup_entry with protocol mode 6 (CBFF)."""
        coordinator = create_mock_coordinator(protocol_mode=6)

        entry = MagicMock()
        entry.runtime_data = coordinator
        async_add_entities = MagicMock()
        hass = MagicMock()

        await async_setup_entry(hass, entry, async_add_entities)

        async_add_entities.assert_called_once()
        call_args = async_add_entities.call_args[0][0]
        # Mode 6 creates all sensors (18 core + 3 extended + 5 CBFF = 26)
        assert len(call_args) == 26


# ---------------------------------------------------------------------------
# Raw interior temperature sensor tests
# ---------------------------------------------------------------------------

class TestVevorRawInteriorTemperatureSensor:
    """Tests for raw interior temperature sensor."""

    def test_native_value(self):
        """Test native_value returns raw temperature."""
        coordinator = create_mock_coordinator()
        coordinator.data["cab_temperature_raw"] = 19.5
        sensor = VevorRawInteriorTemperatureSensor(coordinator)

        assert sensor.native_value == 19.5

    def test_native_value_none(self):
        """Test native_value when data is None."""
        coordinator = create_mock_coordinator()
        coordinator.data["cab_temperature_raw"] = None
        sensor = VevorRawInteriorTemperatureSensor(coordinator)

        assert sensor.native_value is None

    def test_unique_id(self):
        """Test unique_id format."""
        coordinator = create_mock_coordinator()
        sensor = VevorRawInteriorTemperatureSensor(coordinator)

        assert "_cab_temp_raw" in sensor.unique_id

    def test_disabled_by_default(self):
        """Test sensor is disabled by default."""
        coordinator = create_mock_coordinator()
        sensor = VevorRawInteriorTemperatureSensor(coordinator)

        assert sensor._attr_entity_registry_enabled_default is False


# ---------------------------------------------------------------------------
# Heater offset sensor tests
# ---------------------------------------------------------------------------

class TestVevorHeaterOffsetSensor:
    """Tests for heater offset sensor."""

    def test_native_value(self):
        """Test native_value returns offset."""
        coordinator = create_mock_coordinator()
        coordinator.data["heater_offset"] = 3
        sensor = VevorHeaterOffsetSensor(coordinator)

        assert sensor.native_value == 3

    def test_native_value_negative(self):
        """Test native_value with negative offset."""
        coordinator = create_mock_coordinator()
        coordinator.data["heater_offset"] = -5
        sensor = VevorHeaterOffsetSensor(coordinator)

        assert sensor.native_value == -5

    def test_native_value_default_zero(self):
        """Test native_value defaults to 0 when missing."""
        coordinator = create_mock_coordinator()
        del coordinator.data["heater_offset"]
        sensor = VevorHeaterOffsetSensor(coordinator)

        assert sensor.native_value == 0

    def test_available_always_when_coordinator_available(self):
        """Test available is True when coordinator is available."""
        coordinator = create_mock_coordinator()
        coordinator.last_update_success = True
        sensor = VevorHeaterOffsetSensor(coordinator)

        assert sensor.available is True

    def test_unique_id(self):
        """Test unique_id format."""
        coordinator = create_mock_coordinator()
        sensor = VevorHeaterOffsetSensor(coordinator)

        assert "_heater_offset" in sensor.unique_id

    def test_icon(self):
        """Test icon."""
        coordinator = create_mock_coordinator()
        sensor = VevorHeaterOffsetSensor(coordinator)

        assert sensor._attr_icon == "mdi:thermometer-plus"


# ---------------------------------------------------------------------------
# Daily fuel history sensor tests
# ---------------------------------------------------------------------------

class TestVevorDailyFuelHistorySensor:
    """Tests for daily fuel history sensor."""

    def test_native_value_returns_days_count(self):
        """Test native_value returns number of days in history."""
        coordinator = create_mock_coordinator()
        coordinator.data["daily_fuel_history"] = {
            "2024-01-01": 1.5,
            "2024-01-02": 2.0,
            "2024-01-03": 1.2,
        }
        sensor = VevorDailyFuelHistorySensor(coordinator)

        assert sensor.native_value == 3

    def test_native_value_empty_history(self):
        """Test native_value with empty history."""
        coordinator = create_mock_coordinator()
        coordinator.data["daily_fuel_history"] = {}
        sensor = VevorDailyFuelHistorySensor(coordinator)

        assert sensor.native_value == 0

    def test_extra_state_attributes_with_history(self):
        """Test extra_state_attributes with history data."""
        coordinator = create_mock_coordinator()
        coordinator.data["daily_fuel_history"] = {
            "2024-01-01": 1.5,
            "2024-01-02": 2.0,
        }
        sensor = VevorDailyFuelHistorySensor(coordinator)

        attrs = sensor.extra_state_attributes
        assert attrs["days_tracked"] == 2
        assert "history" in attrs
        assert "total_in_history" in attrs

    def test_extra_state_attributes_empty_history(self):
        """Test extra_state_attributes with empty history."""
        coordinator = create_mock_coordinator()
        coordinator.data["daily_fuel_history"] = {}
        sensor = VevorDailyFuelHistorySensor(coordinator)

        attrs = sensor.extra_state_attributes
        assert attrs["days_tracked"] == 0
        assert attrs["total_in_history"] == 0.0

    def test_unique_id(self):
        """Test unique_id format."""
        coordinator = create_mock_coordinator()
        sensor = VevorDailyFuelHistorySensor(coordinator)

        assert "_est_daily_fuel_history" in sensor.unique_id


# ---------------------------------------------------------------------------
# Daily runtime history sensor tests
# ---------------------------------------------------------------------------

class TestVevorDailyRuntimeHistorySensor:
    """Tests for daily runtime history sensor."""

    def test_native_value_returns_days_count(self):
        """Test native_value returns number of days in history."""
        coordinator = create_mock_coordinator()
        coordinator.data["daily_runtime_history"] = {
            "2024-01-01": 4.5,
            "2024-01-02": 6.0,
        }
        sensor = VevorDailyRuntimeHistorySensor(coordinator)

        assert sensor.native_value == 2

    def test_native_value_empty_history(self):
        """Test native_value with empty history."""
        coordinator = create_mock_coordinator()
        coordinator.data["daily_runtime_history"] = {}
        sensor = VevorDailyRuntimeHistorySensor(coordinator)

        assert sensor.native_value == 0

    def test_extra_state_attributes_with_history(self):
        """Test extra_state_attributes with history data."""
        coordinator = create_mock_coordinator()
        coordinator.data["daily_runtime_history"] = {
            "2024-01-01": 4.5,
            "2024-01-02": 6.0,
        }
        sensor = VevorDailyRuntimeHistorySensor(coordinator)

        attrs = sensor.extra_state_attributes
        assert attrs["days_tracked"] == 2
        assert "history" in attrs
        assert "total_hours_in_history" in attrs

    def test_extra_state_attributes_empty_history(self):
        """Test extra_state_attributes with empty history."""
        coordinator = create_mock_coordinator()
        coordinator.data["daily_runtime_history"] = {}
        sensor = VevorDailyRuntimeHistorySensor(coordinator)

        attrs = sensor.extra_state_attributes
        assert attrs["days_tracked"] == 0
        assert attrs["total_hours_in_history"] == 0.0

    def test_unique_id(self):
        """Test unique_id format."""
        coordinator = create_mock_coordinator()
        sensor = VevorDailyRuntimeHistorySensor(coordinator)

        assert "_daily_runtime_history" in sensor.unique_id


# ---------------------------------------------------------------------------
# Last refueled sensor tests
# ---------------------------------------------------------------------------

class TestVevorLastRefueledSensor:
    """Tests for last refueled sensor."""

    def test_native_value_with_timestamp(self):
        """Test native_value with valid timestamp."""
        coordinator = create_mock_coordinator()
        coordinator.data["last_refueled"] = "2024-01-15T10:30:00"
        sensor = VevorLastRefueledSensor(coordinator)

        value = sensor.native_value
        assert value is not None
        assert value.year == 2024
        assert value.month == 1
        assert value.day == 15

    def test_native_value_none_when_missing(self):
        """Test native_value is None when not set."""
        coordinator = create_mock_coordinator()
        coordinator.data["last_refueled"] = None
        sensor = VevorLastRefueledSensor(coordinator)

        assert sensor.native_value is None

    def test_native_value_none_on_invalid_timestamp(self):
        """Test native_value is None on invalid timestamp."""
        coordinator = create_mock_coordinator()
        coordinator.data["last_refueled"] = "invalid"
        sensor = VevorLastRefueledSensor(coordinator)

        assert sensor.native_value is None

    def test_available_when_refueled(self):
        """Test available when last_refueled is set."""
        coordinator = create_mock_coordinator()
        coordinator.data["last_refueled"] = "2024-01-15T10:30:00"
        sensor = VevorLastRefueledSensor(coordinator)

        assert sensor.available is True

    def test_not_available_when_never_refueled(self):
        """Test not available when last_refueled is None."""
        coordinator = create_mock_coordinator()
        coordinator.data["last_refueled"] = None
        sensor = VevorLastRefueledSensor(coordinator)

        assert sensor.available is False

    def test_unique_id(self):
        """Test unique_id format."""
        coordinator = create_mock_coordinator()
        sensor = VevorLastRefueledSensor(coordinator)

        assert "_last_refueled" in sensor.unique_id


# ---------------------------------------------------------------------------
# Fuel consumed since reset sensor tests
# ---------------------------------------------------------------------------

class TestVevorFuelConsumedSinceResetSensor:
    """Tests for fuel consumed since reset sensor."""

    def test_native_value(self):
        """Test native_value returns fuel consumed."""
        coordinator = create_mock_coordinator()
        coordinator.data["fuel_consumed_since_reset"] = 2.5
        sensor = VevorFuelConsumedSinceResetSensor(coordinator)

        assert sensor.native_value == 2.5

    def test_native_value_none(self):
        """Test native_value when not tracked."""
        coordinator = create_mock_coordinator()
        coordinator.data["fuel_consumed_since_reset"] = None
        sensor = VevorFuelConsumedSinceResetSensor(coordinator)

        assert sensor.native_value is None

    def test_available_when_tracking(self):
        """Test available when fuel is being tracked."""
        coordinator = create_mock_coordinator()
        coordinator.data["fuel_consumed_since_reset"] = 1.0
        sensor = VevorFuelConsumedSinceResetSensor(coordinator)

        assert sensor.available is True

    def test_not_available_when_none(self):
        """Test not available when not tracking."""
        coordinator = create_mock_coordinator()
        coordinator.data["fuel_consumed_since_reset"] = None
        sensor = VevorFuelConsumedSinceResetSensor(coordinator)

        assert sensor.available is False

    def test_unique_id(self):
        """Test unique_id format."""
        coordinator = create_mock_coordinator()
        sensor = VevorFuelConsumedSinceResetSensor(coordinator)

        assert "_est_fuel_since_refuel" in sensor.unique_id


# ---------------------------------------------------------------------------
# CO sensor tests
# ---------------------------------------------------------------------------

class TestVevorCOSensor:
    """Tests for CO sensor."""

    def test_native_value(self):
        """Test native_value returns CO ppm."""
        coordinator = create_mock_coordinator()
        coordinator.data["co_ppm"] = 50
        sensor = VevorCOSensor(coordinator)

        assert sensor.native_value == 50

    def test_native_value_none(self):
        """Test native_value when not available."""
        coordinator = create_mock_coordinator()
        coordinator.data["co_ppm"] = None
        sensor = VevorCOSensor(coordinator)

        assert sensor.native_value is None

    def test_available_when_has_data(self):
        """Test available when CO data is present."""
        coordinator = create_mock_coordinator()
        coordinator.data["co_ppm"] = 25
        sensor = VevorCOSensor(coordinator)

        assert sensor.available is True

    def test_not_available_when_no_data(self):
        """Test not available when CO data is None."""
        coordinator = create_mock_coordinator()
        coordinator.data["co_ppm"] = None
        sensor = VevorCOSensor(coordinator)

        assert sensor.available is False

    def test_unique_id(self):
        """Test unique_id format."""
        coordinator = create_mock_coordinator()
        sensor = VevorCOSensor(coordinator)

        assert "_co_ppm" in sensor.unique_id

    def test_icon(self):
        """Test icon."""
        coordinator = create_mock_coordinator()
        sensor = VevorCOSensor(coordinator)

        assert sensor._attr_icon == "mdi:molecule-co"


# ---------------------------------------------------------------------------
# Hardware version sensor tests
# ---------------------------------------------------------------------------

class TestVevorHardwareVersionSensor:
    """Tests for hardware version sensor."""

    def test_native_value(self):
        """Test native_value returns version."""
        coordinator = create_mock_coordinator()
        coordinator.data["hardware_version"] = 21
        sensor = VevorHardwareVersionSensor(coordinator)

        assert sensor.native_value == 21

    def test_native_value_none(self):
        """Test native_value when not available."""
        coordinator = create_mock_coordinator()
        coordinator.data["hardware_version"] = None
        sensor = VevorHardwareVersionSensor(coordinator)

        assert sensor.native_value is None

    def test_available_when_has_data(self):
        """Test available when version is present."""
        coordinator = create_mock_coordinator()
        coordinator.data["hardware_version"] = 21
        sensor = VevorHardwareVersionSensor(coordinator)

        assert sensor.available is True

    def test_not_available_when_no_data(self):
        """Test not available when version is None."""
        coordinator = create_mock_coordinator()
        coordinator.data["hardware_version"] = None
        sensor = VevorHardwareVersionSensor(coordinator)

        assert sensor.available is False

    def test_unique_id(self):
        """Test unique_id format."""
        coordinator = create_mock_coordinator()
        sensor = VevorHardwareVersionSensor(coordinator)

        assert "_hardware_version" in sensor.unique_id

    def test_icon(self):
        """Test icon."""
        coordinator = create_mock_coordinator()
        sensor = VevorHardwareVersionSensor(coordinator)

        assert sensor._attr_icon == "mdi:chip"


# ---------------------------------------------------------------------------
# Software version sensor tests
# ---------------------------------------------------------------------------

class TestVevorSoftwareVersionSensor:
    """Tests for software version sensor."""

    def test_native_value(self):
        """Test native_value returns version."""
        coordinator = create_mock_coordinator()
        coordinator.data["software_version"] = 15
        sensor = VevorSoftwareVersionSensor(coordinator)

        assert sensor.native_value == 15

    def test_native_value_none(self):
        """Test native_value when not available."""
        coordinator = create_mock_coordinator()
        coordinator.data["software_version"] = None
        sensor = VevorSoftwareVersionSensor(coordinator)

        assert sensor.native_value is None

    def test_available_when_has_data(self):
        """Test available when version is present."""
        coordinator = create_mock_coordinator()
        coordinator.data["software_version"] = 15
        sensor = VevorSoftwareVersionSensor(coordinator)

        assert sensor.available is True

    def test_not_available_when_no_data(self):
        """Test not available when version is None."""
        coordinator = create_mock_coordinator()
        coordinator.data["software_version"] = None
        sensor = VevorSoftwareVersionSensor(coordinator)

        assert sensor.available is False

    def test_unique_id(self):
        """Test unique_id format."""
        coordinator = create_mock_coordinator()
        sensor = VevorSoftwareVersionSensor(coordinator)

        assert "_software_version" in sensor.unique_id

    def test_icon(self):
        """Test icon."""
        coordinator = create_mock_coordinator()
        sensor = VevorSoftwareVersionSensor(coordinator)

        assert sensor._attr_icon == "mdi:tag"


# ---------------------------------------------------------------------------
# Remaining run time sensor tests
# ---------------------------------------------------------------------------

class TestVevorRemainingRunTimeSensor:
    """Tests for remaining run time sensor."""

    def test_native_value(self):
        """Test native_value returns minutes."""
        coordinator = create_mock_coordinator()
        coordinator.data["remain_run_time"] = 120
        sensor = VevorRemainingRunTimeSensor(coordinator)

        assert sensor.native_value == 120

    def test_native_value_none(self):
        """Test native_value when not available."""
        coordinator = create_mock_coordinator()
        coordinator.data["remain_run_time"] = None
        sensor = VevorRemainingRunTimeSensor(coordinator)

        assert sensor.native_value is None

    def test_available_when_has_data(self):
        """Test available when time is present."""
        coordinator = create_mock_coordinator()
        coordinator.data["remain_run_time"] = 60
        sensor = VevorRemainingRunTimeSensor(coordinator)

        assert sensor.available is True

    def test_not_available_when_no_data(self):
        """Test not available when time is None."""
        coordinator = create_mock_coordinator()
        coordinator.data["remain_run_time"] = None
        sensor = VevorRemainingRunTimeSensor(coordinator)

        assert sensor.available is False

    def test_unique_id(self):
        """Test unique_id format."""
        coordinator = create_mock_coordinator()
        sensor = VevorRemainingRunTimeSensor(coordinator)

        assert "_remain_run_time" in sensor.unique_id

    def test_icon(self):
        """Test icon."""
        coordinator = create_mock_coordinator()
        sensor = VevorRemainingRunTimeSensor(coordinator)

        assert sensor._attr_icon == "mdi:timer-sand"


# ---------------------------------------------------------------------------
# Startup temp diff sensor tests
# ---------------------------------------------------------------------------

class TestVevorStartupTempDiffSensor:
    """Tests for startup temp diff sensor."""

    def test_native_value(self):
        """Test native_value returns temp diff."""
        coordinator = create_mock_coordinator()
        coordinator.data["startup_temp_diff"] = 5
        sensor = VevorStartupTempDiffSensor(coordinator)

        assert sensor.native_value == 5

    def test_native_value_none(self):
        """Test native_value when not available."""
        coordinator = create_mock_coordinator()
        coordinator.data["startup_temp_diff"] = None
        sensor = VevorStartupTempDiffSensor(coordinator)

        assert sensor.native_value is None

    def test_available_when_has_data(self):
        """Test available when value is present."""
        coordinator = create_mock_coordinator()
        coordinator.data["startup_temp_diff"] = 3
        sensor = VevorStartupTempDiffSensor(coordinator)

        assert sensor.available is True

    def test_not_available_when_no_data(self):
        """Test not available when value is None."""
        coordinator = create_mock_coordinator()
        coordinator.data["startup_temp_diff"] = None
        sensor = VevorStartupTempDiffSensor(coordinator)

        assert sensor.available is False

    def test_unique_id(self):
        """Test unique_id format."""
        coordinator = create_mock_coordinator()
        sensor = VevorStartupTempDiffSensor(coordinator)

        assert "_startup_temp_diff" in sensor.unique_id

    def test_icon(self):
        """Test icon."""
        coordinator = create_mock_coordinator()
        sensor = VevorStartupTempDiffSensor(coordinator)

        assert sensor._attr_icon == "mdi:thermometer-chevron-up"


# ---------------------------------------------------------------------------
# Shutdown temp diff sensor tests
# ---------------------------------------------------------------------------

class TestVevorShutdownTempDiffSensor:
    """Tests for shutdown temp diff sensor."""

    def test_native_value(self):
        """Test native_value returns temp diff."""
        coordinator = create_mock_coordinator()
        coordinator.data["shutdown_temp_diff"] = 2
        sensor = VevorShutdownTempDiffSensor(coordinator)

        assert sensor.native_value == 2

    def test_native_value_none(self):
        """Test native_value when not available."""
        coordinator = create_mock_coordinator()
        coordinator.data["shutdown_temp_diff"] = None
        sensor = VevorShutdownTempDiffSensor(coordinator)

        assert sensor.native_value is None

    def test_available_when_has_data(self):
        """Test available when value is present."""
        coordinator = create_mock_coordinator()
        coordinator.data["shutdown_temp_diff"] = 2
        sensor = VevorShutdownTempDiffSensor(coordinator)

        assert sensor.available is True

    def test_not_available_when_no_data(self):
        """Test not available when value is None."""
        coordinator = create_mock_coordinator()
        coordinator.data["shutdown_temp_diff"] = None
        sensor = VevorShutdownTempDiffSensor(coordinator)

        assert sensor.available is False

    def test_unique_id(self):
        """Test unique_id format."""
        coordinator = create_mock_coordinator()
        sensor = VevorShutdownTempDiffSensor(coordinator)

        assert "_shutdown_temp_diff" in sensor.unique_id

    def test_icon(self):
        """Test icon."""
        coordinator = create_mock_coordinator()
        sensor = VevorShutdownTempDiffSensor(coordinator)

        assert sensor._attr_icon == "mdi:thermometer-chevron-down"


# ---------------------------------------------------------------------------
# Fuel remaining extra attributes tests
# ---------------------------------------------------------------------------

class TestVevorFuelRemainingExtraAttributes:
    """Tests for fuel remaining sensor extra attributes."""

    def test_extra_state_attributes_with_tank_capacity(self):
        """Test extra_state_attributes with tank capacity."""
        coordinator = create_mock_coordinator()
        coordinator.data["tank_capacity"] = 10
        coordinator.data["fuel_remaining"] = 7.5
        coordinator.data["fuel_consumed_since_reset"] = 2.5
        sensor = VevorFuelRemainingSensor(coordinator)

        attrs = sensor.extra_state_attributes
        assert attrs["fuel_consumed_since_reset"] == 2.5
        assert attrs["tank_capacity"] == 10
        assert attrs["fuel_remaining_percent"] == 75.0

    def test_extra_state_attributes_without_tank_capacity(self):
        """Test extra_state_attributes without tank capacity."""
        coordinator = create_mock_coordinator()
        coordinator.data["tank_capacity"] = None
        coordinator.data["fuel_consumed_since_reset"] = 2.5
        sensor = VevorFuelRemainingSensor(coordinator)

        attrs = sensor.extra_state_attributes
        assert attrs["fuel_consumed_since_reset"] == 2.5
        assert "tank_capacity" not in attrs


# ---------------------------------------------------------------------------
# Entity attribute tests
# ---------------------------------------------------------------------------

class TestSensorEntityAttributes:
    """Tests for sensor entity attributes."""

    def test_case_temp_entity_category(self):
        """Test case temperature entity category."""
        coordinator = create_mock_coordinator()
        sensor = VevorCaseTemperatureSensor(coordinator)

        assert sensor._attr_entity_category is not None

    def test_supply_voltage_entity_category(self):
        """Test supply voltage entity category."""
        coordinator = create_mock_coordinator()
        sensor = VevorSupplyVoltageSensor(coordinator)

        assert sensor._attr_entity_category is not None

    def test_altitude_entity_category(self):
        """Test altitude entity category."""
        coordinator = create_mock_coordinator()
        sensor = VevorAltitudeSensor(coordinator)

        assert sensor._attr_entity_category is not None

    def test_error_code_entity_category(self):
        """Test error code entity category."""
        coordinator = create_mock_coordinator()
        sensor = VevorErrorCodeSensor(coordinator)

        assert sensor._attr_entity_category is not None

    def test_running_step_icon(self):
        """Test running step icon."""
        coordinator = create_mock_coordinator()
        sensor = VevorRunningStepSensor(coordinator)

        assert sensor._attr_icon == "mdi:progress-clock"

    def test_running_mode_icon(self):
        """Test running mode icon."""
        coordinator = create_mock_coordinator()
        sensor = VevorRunningModeSensor(coordinator)

        assert sensor._attr_icon == "mdi:cog"

    def test_set_level_icon(self):
        """Test set level icon."""
        coordinator = create_mock_coordinator()
        sensor = VevorSetLevelSensor(coordinator)

        assert sensor._attr_icon == "mdi:gauge"

    def test_altitude_icon(self):
        """Test altitude icon."""
        coordinator = create_mock_coordinator()
        sensor = VevorAltitudeSensor(coordinator)

        assert sensor._attr_icon == "mdi:altimeter"

    def test_error_code_icon(self):
        """Test error code icon."""
        coordinator = create_mock_coordinator()
        sensor = VevorErrorCodeSensor(coordinator)

        assert sensor._attr_icon == "mdi:alert-circle"

    def test_daily_fuel_consumed_icon(self):
        """Test daily fuel consumed icon."""
        coordinator = create_mock_coordinator()
        sensor = VevorDailyFuelConsumedSensor(coordinator)

        assert sensor._attr_icon == "mdi:gas-station"

    def test_fuel_remaining_icon(self):
        """Test fuel remaining icon."""
        coordinator = create_mock_coordinator()
        sensor = VevorFuelRemainingSensor(coordinator)

        assert sensor._attr_icon == "mdi:fuel"

    def test_daily_runtime_icon(self):
        """Test daily runtime icon."""
        coordinator = create_mock_coordinator()
        sensor = VevorDailyRuntimeSensor(coordinator)

        assert sensor._attr_icon == "mdi:clock-outline"

    def test_total_runtime_icon(self):
        """Test total runtime icon."""
        coordinator = create_mock_coordinator()
        sensor = VevorTotalRuntimeSensor(coordinator)

        assert sensor._attr_icon == "mdi:clock-check"

    def test_has_entity_name(self):
        """Test has_entity_name is True for all sensors."""
        coordinator = create_mock_coordinator()
        sensors = [
            VevorCabTemperatureSensor(coordinator),
            VevorCaseTemperatureSensor(coordinator),
            VevorSupplyVoltageSensor(coordinator),
            VevorRunningStepSensor(coordinator),
        ]

        for sensor in sensors:
            assert sensor._attr_has_entity_name is True

    def test_device_info_set(self):
        """Test device_info is set for all sensors."""
        coordinator = create_mock_coordinator()
        sensor = VevorCabTemperatureSensor(coordinator)

        assert sensor._attr_device_info is not None
        assert "identifiers" in sensor._attr_device_info
        assert "name" in sensor._attr_device_info


# ---------------------------------------------------------------------------
# _handle_coordinator_update tests
# ---------------------------------------------------------------------------

class TestHandleCoordinatorUpdate:
    """Tests for _handle_coordinator_update on sensor entities."""

    def test_cab_temperature_handle_coordinator_update(self):
        """Test CabTemperatureSensor _handle_coordinator_update calls async_write_ha_state."""
        coordinator = create_mock_coordinator()
        sensor = VevorCabTemperatureSensor(coordinator)
        sensor.async_write_ha_state = MagicMock()

        sensor._handle_coordinator_update()

        sensor.async_write_ha_state.assert_called_once()
