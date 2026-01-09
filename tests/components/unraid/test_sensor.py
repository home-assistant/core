"""Tests for Unraid sensor entities."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.components.unraid import UnraidRuntimeData
from homeassistant.components.unraid.binary_sensor import (
    ArrayStartedBinarySensor,
    DiskHealthBinarySensor,
    ParityCheckRunningBinarySensor,
    ParityValidBinarySensor,
)
from homeassistant.components.unraid.const import (
    CONF_UPS_CAPACITY_VA,
    CONF_UPS_NOMINAL_POWER,
    DOMAIN,
)
from homeassistant.components.unraid.coordinator import (
    UnraidStorageCoordinator,
    UnraidSystemCoordinator,
)
from homeassistant.components.unraid.models import (
    ArrayCapacity,
    ArrayDisk,
    CapacityKilobytes,
    ParityCheck,
    Share,
    UPSBattery,
    UPSDevice,
    UPSPower,
)
from homeassistant.components.unraid.sensor import (
    ActiveNotificationsSensor,
    ArrayStateSensor,
    ArrayUsageSensor,
    CpuPowerSensor,
    CpuSensor,
    DiskTemperatureSensor,
    DiskUsageSensor,
    FlashUsageSensor,
    ParityProgressSensor,
    RAMUsageSensor,
    ShareUsageSensor,
    TemperatureSensor,
    UnraidSensorEntity,
    UPSBatterySensor,
    UPSLoadSensor,
    UPSPowerSensor,
    UPSRuntimeSensor,
    UptimeSensor,
    async_setup_entry,
    format_bytes,
    format_uptime,
)
from homeassistant.const import UnitOfPower
from homeassistant.helpers.entity import EntityCategory

from .conftest import make_storage_data, make_system_data

# =============================================================================
# Helper Function Tests
# =============================================================================


class TestFormatBytes:
    """Test format_bytes helper function."""

    def test_format_bytes_none(self) -> None:
        """Test format_bytes returns None for None input."""
        assert format_bytes(None) is None

    def test_format_bytes_zero(self) -> None:
        """Test format_bytes returns '0 B' for zero."""
        assert format_bytes(0) == "0 B"

    def test_format_bytes_bytes(self) -> None:
        """Test format_bytes for byte values (< 1024)."""
        assert format_bytes(100) == "100 B"
        assert format_bytes(1023) == "1023 B"

    def test_format_bytes_kilobytes(self) -> None:
        """Test format_bytes for KB values."""
        assert format_bytes(1024) == "1.00 KB"
        assert format_bytes(2048) == "2.00 KB"

    def test_format_bytes_megabytes(self) -> None:
        """Test format_bytes for MB values."""
        assert format_bytes(1048576) == "1.00 MB"

    def test_format_bytes_gigabytes(self) -> None:
        """Test format_bytes for GB values."""
        assert format_bytes(1073741824) == "1.00 GB"

    def test_format_bytes_terabytes(self) -> None:
        """Test format_bytes for TB values."""
        assert format_bytes(1099511627776) == "1.00 TB"

    def test_format_bytes_petabytes(self) -> None:
        """Test format_bytes for PB values."""
        assert format_bytes(1125899906842624) == "1.00 PB"

    def test_format_bytes_large_value(self) -> None:
        """Test format_bytes doesn't go beyond PB."""
        # 2000 PB should still display as PB
        assert "PB" in format_bytes(2 * 1125899906842624)


class TestFormatUptime:
    """Test format_uptime helper function."""

    def test_format_uptime_none(self) -> None:
        """Test format_uptime returns None for None input."""
        assert format_uptime(None) is None

    def test_format_uptime_future_date(self) -> None:
        """Test format_uptime returns '0 seconds' for future dates."""
        future = datetime.now(UTC) + timedelta(hours=1)
        assert format_uptime(future) == "0 seconds"

    def test_format_uptime_seconds(self) -> None:
        """Test format_uptime for seconds only."""
        past = datetime.now(UTC) - timedelta(seconds=30)
        result = format_uptime(past)
        assert "30 seconds" in result

    def test_format_uptime_minutes(self) -> None:
        """Test format_uptime for minutes."""
        past = datetime.now(UTC) - timedelta(minutes=5, seconds=30)
        result = format_uptime(past)
        assert "5 minutes" in result
        assert "30 second" in result

    def test_format_uptime_hours(self) -> None:
        """Test format_uptime for hours."""
        past = datetime.now(UTC) - timedelta(hours=2, minutes=15)
        result = format_uptime(past)
        assert "2 hours" in result
        assert "15 minute" in result

    def test_format_uptime_days(self) -> None:
        """Test format_uptime for days."""
        past = datetime.now(UTC) - timedelta(days=3, hours=12)
        result = format_uptime(past)
        assert "3 days" in result
        assert "12 hour" in result

    def test_format_uptime_months(self) -> None:
        """Test format_uptime for months."""
        past = datetime.now(UTC) - timedelta(days=45)
        result = format_uptime(past)
        assert "month" in result

    def test_format_uptime_years(self) -> None:
        """Test format_uptime for years."""
        past = datetime.now(UTC) - timedelta(days=400)
        result = format_uptime(past)
        assert "year" in result

    def test_format_uptime_singular(self) -> None:
        """Test format_uptime uses singular form."""
        past = datetime.now(UTC) - timedelta(days=1, hours=1, minutes=1, seconds=1)
        result = format_uptime(past)
        assert "1 day" in result
        assert "1 hour" in result
        assert "1 minute" in result
        assert "1 second" in result

    def test_format_uptime_zero_parts(self) -> None:
        """Test format_uptime with zero intermediate parts."""
        # Just a few seconds - should only show seconds
        past = datetime.now(UTC) - timedelta(seconds=5)
        result = format_uptime(past)
        assert "second" in result
        assert "minute" not in result


# =============================================================================
# Base Entity Tests
# =============================================================================


class TestUnraidSensorEntity:
    """Test UnraidSensorEntity base class."""

    def test_base_sensor_entity_properties(self) -> None:
        """Test base sensor entity has proper device info."""
        entity = UnraidSensorEntity(
            coordinator=MagicMock(spec=UnraidSystemCoordinator),
            server_uuid="test-uuid",
            server_name="test-server",
            resource_id="test-resource",
            name="Test Sensor",
        )

        assert entity.unique_id == "test-uuid_test-resource"
        assert entity.name == "Test Sensor"
        assert entity.device_info is not None
        assert entity.device_info["identifiers"] == {(DOMAIN, "test-uuid")}
        assert entity.device_info["name"] == "test-server"

    def test_sensor_availability_from_coordinator(self) -> None:
        """Test sensor availability based on coordinator."""
        coordinator = MagicMock(spec=UnraidSystemCoordinator)
        coordinator.last_update_success = True

        entity = UnraidSensorEntity(
            coordinator=coordinator,
            server_uuid="test-uuid",
            server_name="test-server",
            resource_id="test-resource",
            name="Test Sensor",
        )

        assert entity.available is True

        coordinator.last_update_success = False
        assert entity.available is False


class TestCpuSensor:
    """Test CPU usage sensor."""

    def test_cpu_sensor_creation(self) -> None:
        """Test CPU sensor creation with proper attributes."""
        coordinator = MagicMock(spec=UnraidSystemCoordinator)
        coordinator.data = make_system_data(cpu_percent=45.2)

        sensor = CpuSensor(
            coordinator=coordinator,
            server_uuid="test-uuid",
            server_name="test-server",
        )

        assert sensor.unique_id == "test-uuid_cpu_usage"
        assert sensor.name == "CPU Usage"
        assert sensor.device_class is None
        assert sensor.state_class == SensorStateClass.MEASUREMENT
        assert sensor.native_unit_of_measurement == "%"
        assert sensor.translation_key == "cpu_usage"

    def test_cpu_sensor_state(self) -> None:
        """Test CPU sensor returns correct state."""
        coordinator = MagicMock(spec=UnraidSystemCoordinator)
        coordinator.data = make_system_data(cpu_percent=45.2)

        sensor = CpuSensor(
            coordinator=coordinator,
            server_uuid="test-uuid",
            server_name="test-server",
        )

        assert sensor.native_value == 45.2

    def test_cpu_sensor_missing_data(self) -> None:
        """Test CPU sensor handles missing data."""
        coordinator = MagicMock(spec=UnraidSystemCoordinator)
        coordinator.data = make_system_data(cpu_percent=None)

        sensor = CpuSensor(
            coordinator=coordinator,
            server_uuid="test-uuid",
            server_name="test-server",
        )

        assert sensor.native_value is None


class TestRAMSensor:
    """Test RAM usage sensor."""

    def test_ram_usage_sensor_creation(self) -> None:
        """Test RAM usage sensor creation."""
        coordinator = MagicMock(spec=UnraidSystemCoordinator)
        coordinator.data = make_system_data(
            memory_total=16000000000, memory_used=8000000000, memory_percent=50.0
        )

        sensor = RAMUsageSensor(
            coordinator=coordinator,
            server_uuid="test-uuid",
            server_name="test-server",
        )

        assert sensor.unique_id == "test-uuid_ram_usage"
        assert sensor.device_class is None
        assert sensor.state_class == SensorStateClass.MEASUREMENT
        assert sensor.native_unit_of_measurement == "%"
        assert sensor.translation_key == "ram_usage"

    def test_ram_usage_sensor_state(self) -> None:
        """Test RAM usage sensor returns correct percentage state."""
        coordinator = MagicMock(spec=UnraidSystemCoordinator)
        coordinator.data = make_system_data(
            memory_total=16000000000,
            memory_used=8000000000,
            memory_percent=50.0,
        )

        sensor = RAMUsageSensor(
            coordinator=coordinator,
            server_uuid="test-uuid",
            server_name="test-server",
        )

        assert sensor.native_value == 50.0

    def test_ram_usage_sensor_attributes(self) -> None:
        """Test RAM usage sensor returns human-readable attributes."""
        coordinator = MagicMock(spec=UnraidSystemCoordinator)
        coordinator.data = make_system_data(
            memory_total=17179869184,  # 16 GB
            memory_used=8589934592,  # 8 GB
            memory_percent=50.0,
        )
        # Add free and available values
        coordinator.data.metrics.memory.free = 8589934592
        coordinator.data.metrics.memory.available = 10000000000

        sensor = RAMUsageSensor(
            coordinator=coordinator,
            server_uuid="test-uuid",
            server_name="test-server",
        )

        attrs = sensor.extra_state_attributes
        assert "total" in attrs
        assert "used" in attrs
        assert "free" in attrs
        assert "available" in attrs
        # Check human-readable format (should be GB)
        assert "GB" in attrs["total"]


class TestTemperatureSensor:
    """Test CPU temperature sensor."""

    def test_temperature_sensor_creation(self) -> None:
        """Test temperature sensor creation."""
        coordinator = MagicMock(spec=UnraidSystemCoordinator)
        coordinator.data = make_system_data(cpu_temps=[45.0])

        sensor = TemperatureSensor(
            coordinator=coordinator,
            server_uuid="test-uuid",
            server_name="test-server",
        )

        assert sensor.unique_id == "test-uuid_cpu_temp"
        assert sensor.device_class == SensorDeviceClass.TEMPERATURE
        assert sensor.state_class == SensorStateClass.MEASUREMENT
        assert sensor.native_unit_of_measurement == "°C"

    def test_temperature_sensor_state(self) -> None:
        """Test temperature sensor returns correct state (average of all packages)."""
        cpu_temps = [45.0, 50.0, 48.0]
        coordinator = MagicMock(spec=UnraidSystemCoordinator)
        coordinator.data = make_system_data(cpu_temps=cpu_temps)

        sensor = TemperatureSensor(
            coordinator=coordinator,
            server_uuid="test-uuid",
            server_name="test-server",
        )

        # Should average temperatures: (45.0 + 50.0 + 48.0) / 3 = 47.666...
        expected_avg = sum(cpu_temps) / len(cpu_temps)
        assert sensor.native_value == pytest.approx(expected_avg, rel=0.01)

    def test_temperature_sensor_single_value(self) -> None:
        """Test temperature sensor with single CPU package."""
        coordinator = MagicMock(spec=UnraidSystemCoordinator)
        coordinator.data = make_system_data(cpu_temps=[52.5])

        sensor = TemperatureSensor(
            coordinator=coordinator,
            server_uuid="test-uuid",
            server_name="test-server",
        )

        assert sensor.native_value == 52.5

    def test_temperature_sensor_missing_data(self) -> None:
        """Test temperature sensor handles missing data."""
        coordinator = MagicMock(spec=UnraidSystemCoordinator)
        coordinator.data = make_system_data(cpu_temps=[])

        sensor = TemperatureSensor(
            coordinator=coordinator,
            server_uuid="test-uuid",
            server_name="test-server",
        )

        assert sensor.native_value is None


class TestUptimeSensor:
    """Test uptime sensor."""

    def test_uptime_sensor_creation(self) -> None:
        """Test uptime sensor creation."""
        coordinator = MagicMock(spec=UnraidSystemCoordinator)
        coordinator.data = make_system_data(
            uptime=datetime(2025, 12, 20, 12, 0, 0, tzinfo=UTC)
        )

        sensor = UptimeSensor(
            coordinator=coordinator,
            server_uuid="test-uuid",
            server_name="test-server",
        )

        assert sensor.unique_id == "test-uuid_uptime"
        assert sensor.device_class is None  # Changed from TIMESTAMP
        assert sensor.state_class is None
        assert sensor.entity_category == EntityCategory.DIAGNOSTIC

    def test_uptime_sensor_state(self) -> None:
        """Test uptime sensor returns human-readable string."""
        # Boot time 3 days, 2 hours, 30 minutes ago
        uptime_dt = datetime(2025, 12, 20, 9, 30, 0, tzinfo=UTC)
        coordinator = MagicMock(spec=UnraidSystemCoordinator)
        coordinator.data = make_system_data(uptime=uptime_dt)

        sensor = UptimeSensor(
            coordinator=coordinator,
            server_uuid="test-uuid",
            server_name="test-server",
        )

        # Should return human-readable string (actual value depends on "now")
        assert sensor.native_value is not None
        assert isinstance(sensor.native_value, str)


class TestArraySensor:
    """Test array state sensor."""

    def test_array_state_sensor_creation(self) -> None:
        """Test array state sensor creation."""
        coordinator = MagicMock(spec=UnraidStorageCoordinator)
        coordinator.data = make_storage_data(
            array_state="STARTED",
            capacity=ArrayCapacity(
                kilobytes=CapacityKilobytes(total=1000, used=500, free=500)
            ),
        )

        sensor = ArrayStateSensor(
            coordinator=coordinator,
            server_uuid="test-uuid",
            server_name="test-server",
        )

        assert sensor.unique_id == "test-uuid_array_state"
        assert sensor.name == "Array State"
        assert sensor.translation_key == "array_state"

    def test_array_state_sensor_state(self) -> None:
        """Test array state sensor returns correct state."""
        coordinator = MagicMock(spec=UnraidStorageCoordinator)
        coordinator.data = make_storage_data(
            array_state="STARTED",
            capacity=ArrayCapacity(
                kilobytes=CapacityKilobytes(total=1000, used=500, free=500)
            ),
        )

        sensor = ArrayStateSensor(
            coordinator=coordinator,
            server_uuid="test-uuid",
            server_name="test-server",
        )

        assert sensor.native_value == "started"


class TestArrayCapacitySensors:
    """Test array capacity sensors."""

    def test_array_usage_sensor_creation(self) -> None:
        """Test array usage sensor creation."""
        coordinator = MagicMock(spec=UnraidStorageCoordinator)
        coordinator.data = make_storage_data(
            array_state="STARTED",
            capacity=ArrayCapacity(
                kilobytes=CapacityKilobytes(
                    total=10737418240, used=5368709120, free=5368709120
                )
            ),
        )

        sensor = ArrayUsageSensor(
            coordinator=coordinator,
            server_uuid="test-uuid",
            server_name="test-server",
        )

        assert sensor.unique_id == "test-uuid_array_usage"
        assert sensor.native_unit_of_measurement == "%"
        assert sensor.state_class == SensorStateClass.MEASUREMENT
        assert sensor.device_class is None

    def test_array_usage_sensor_state(self) -> None:
        """Test array usage sensor returns percentage value."""
        coordinator = MagicMock(spec=UnraidStorageCoordinator)
        coordinator.data = make_storage_data(
            array_state="STARTED",
            capacity=ArrayCapacity(
                kilobytes=CapacityKilobytes(
                    total=10737418240, used=5368709120, free=5368709120
                )
            ),
        )

        sensor = ArrayUsageSensor(
            coordinator=coordinator,
            server_uuid="test-uuid",
            server_name="test-server",
        )

        assert sensor.native_value == 50.0

    def test_array_usage_sensor_attributes(self) -> None:
        """Test array usage sensor has human-readable attributes."""
        coordinator = MagicMock(spec=UnraidStorageCoordinator)
        coordinator.data = make_storage_data(
            array_state="STARTED",
            capacity=ArrayCapacity(
                kilobytes=CapacityKilobytes(
                    total=10737418240, used=5368709120, free=5368709120
                )
            ),
        )

        sensor = ArrayUsageSensor(
            coordinator=coordinator,
            server_uuid="test-uuid",
            server_name="test-server",
        )

        attrs = sensor.extra_state_attributes
        assert "total" in attrs
        assert "used" in attrs
        assert "free" in attrs
        # Values should be human-readable (GB, TB, etc.)
        assert "TB" in attrs["total"] or "GB" in attrs["total"]


class TestDiskSensors:
    """Test disk sensor entities."""

    def test_disk_temperature_sensor(self) -> None:
        """Test disk temperature sensor creation."""
        disk = ArrayDisk(
            id="disk1",
            idx=0,
            name="disk1",
            device="sda",
            temp=45,
        )
        coordinator = MagicMock(spec=UnraidStorageCoordinator)
        coordinator.data = make_storage_data(disks=[disk])

        sensor = DiskTemperatureSensor(
            coordinator=coordinator,
            server_uuid="test-uuid",
            server_name="test-server",
            disk=disk,
        )

        assert sensor.unique_id == "test-uuid_disk_disk1_temp"
        assert sensor.device_class == SensorDeviceClass.TEMPERATURE
        assert sensor.native_unit_of_measurement == "°C"
        assert sensor.native_value == 45

    def test_disk_usage_sensor(self) -> None:
        """Test disk usage sensor returns percentage."""
        disk = ArrayDisk(
            id="disk1",
            idx=0,
            name="disk1",
            device="sda",
            fs_size=1000,
            fs_used=500,
            fs_free=500,
        )
        coordinator = MagicMock(spec=UnraidStorageCoordinator)
        coordinator.data = make_storage_data(disks=[disk])

        sensor = DiskUsageSensor(
            coordinator=coordinator,
            server_uuid="test-uuid",
            server_name="test-server",
            disk=disk,
        )

        assert sensor.unique_id == "test-uuid_disk_disk1_usage"
        assert sensor.device_class is None  # Changed from DATA_SIZE
        assert sensor.native_unit_of_measurement == "%"
        assert sensor.native_value == 50.0  # 500/1000 * 100

    def test_disk_usage_sensor_attributes(self) -> None:
        """Test disk usage sensor has human-readable attributes."""
        disk = ArrayDisk(
            id="disk1",
            idx=0,
            name="disk1",
            device="sda",
            type="DATA",
            status="DISK_OK",
            fs_size=1000000,  # ~1 GB in KB
            fs_used=500000,
            fs_free=500000,
            is_spinning=True,
            temp=35,
        )
        coordinator = MagicMock(spec=UnraidStorageCoordinator)
        coordinator.data = make_storage_data(disks=[disk])

        sensor = DiskUsageSensor(
            coordinator=coordinator,
            server_uuid="test-uuid",
            server_name="test-server",
            disk=disk,
        )

        attrs = sensor.extra_state_attributes
        assert "total" in attrs
        assert "used" in attrs
        assert "free" in attrs
        assert attrs.get("spin_state") == "active"
        assert "device" in attrs
        assert "type" in attrs
        assert attrs.get("status") == "DISK_OK"
        assert attrs.get("temperature_celsius") == 35

    def test_disk_temperature_missing(self) -> None:
        """Test disk temperature sensor handles missing temperature."""
        disk = ArrayDisk(
            id="disk1",
            idx=0,
            name="disk1",
            device="sda",
            temp=None,
        )
        coordinator = MagicMock(spec=UnraidStorageCoordinator)
        coordinator.data = make_storage_data(disks=[disk])

        sensor = DiskTemperatureSensor(
            coordinator=coordinator,
            server_uuid="test-uuid",
            server_name="test-server",
            disk=disk,
        )

        assert sensor.native_value is None


class TestSensorUpdatesFromCoordinator:
    """Test sensor state updates from coordinator."""

    def test_sensor_updates_on_coordinator_data_change(self) -> None:
        """Test sensor updates when coordinator data changes."""
        # This would be an integration test - testing via async_update_listeners
        # For now, verify the sensor reads from coordinator.data
        coordinator = MagicMock(spec=UnraidSystemCoordinator)
        coordinator.data = make_system_data(cpu_percent=25.0)
        coordinator.last_update_success = True
        coordinator.async_add_listener = MagicMock()

        sensor = CpuSensor(
            coordinator=coordinator,
            server_uuid="test-uuid",
            server_name="test-server",
        )

        assert sensor.native_value == 25.0

        # Simulate data update
        coordinator.data = make_system_data(cpu_percent=75.0)
        assert sensor.native_value == 75.0


class TestParityProgressSensor:
    """Test parity progress sensor."""

    def test_parity_progress_sensor_creation(self) -> None:
        """Test parity progress sensor creation."""
        coordinator = MagicMock(spec=UnraidStorageCoordinator)
        coordinator.data = make_storage_data(
            array_state="STARTED",
            capacity=ArrayCapacity(
                kilobytes=CapacityKilobytes(total=1000, used=500, free=500)
            ),
            parity_status=ParityCheck(status="RUNNING", progress=50, errors=0),
        )

        sensor = ParityProgressSensor(
            coordinator=coordinator,
            server_uuid="test-uuid",
            server_name="test-server",
        )

        assert sensor.unique_id == "test-uuid_parity_progress"
        assert sensor.native_unit_of_measurement == "%"
        assert sensor.native_value == 50


class TestDiskHealthBinarySensor:
    """Test disk health binary sensor."""

    def test_disk_health_binary_sensor_creation(self) -> None:
        """Test disk health binary sensor creation."""
        disk = ArrayDisk(
            id="disk1",
            idx=0,
            name="disk1",
            device="sda",
            status="DISK_OK",
        )
        coordinator = MagicMock(spec=UnraidStorageCoordinator)
        coordinator.data = make_storage_data(disks=[disk])

        sensor = DiskHealthBinarySensor(
            coordinator=coordinator,
            server_uuid="test-uuid",
            server_name="test-server",
            disk=disk,
        )

        assert sensor.unique_id == "test-uuid_disk_health_disk1"
        assert sensor.device_class == "problem"
        assert sensor.name == "Disk disk1 Health"

    def test_disk_health_binary_sensor_ok_status(self) -> None:
        """Test disk health binary sensor is OFF when disk is OK."""
        disk = ArrayDisk(
            id="disk1",
            idx=0,
            name="disk1",
            device="sda",
            status="DISK_OK",
        )
        coordinator = MagicMock(spec=UnraidStorageCoordinator)
        coordinator.data = make_storage_data(disks=[disk])

        sensor = DiskHealthBinarySensor(
            coordinator=coordinator,
            server_uuid="test-uuid",
            server_name="test-server",
            disk=disk,
        )

        # DISK_OK should be OFF (not a problem)
        assert sensor.is_on is False

    def test_disk_health_binary_sensor_problem_status(self) -> None:
        """Test disk health binary sensor is ON when disk has issues."""
        disk = ArrayDisk(
            id="disk1",
            idx=0,
            name="disk1",
            device="sda",
            status="DISK_ERROR",
        )
        coordinator = MagicMock(spec=UnraidStorageCoordinator)
        coordinator.data = make_storage_data(disks=[disk])

        sensor = DiskHealthBinarySensor(
            coordinator=coordinator,
            server_uuid="test-uuid",
            server_name="test-server",
            disk=disk,
        )

        # Any non-DISK_OK status should be ON (is a problem)
        assert sensor.is_on is True


class TestArrayStartedBinarySensor:
    """Test Array Started binary sensor."""

    def test_array_started_sensor_creation(self) -> None:
        """Test array started sensor creation."""
        coordinator = MagicMock(spec=UnraidStorageCoordinator)
        coordinator.data = make_storage_data(array_state="STARTED")

        sensor = ArrayStartedBinarySensor(
            coordinator=coordinator,
            server_uuid="test-uuid",
            server_name="test-server",
        )

        assert sensor.unique_id == "test-uuid_array_started"
        assert sensor.name == "Array Started"

    def test_array_started_sensor_is_on_when_started(self) -> None:
        """Test array started sensor is ON when array is started."""
        coordinator = MagicMock(spec=UnraidStorageCoordinator)
        coordinator.data = make_storage_data(array_state="STARTED")

        sensor = ArrayStartedBinarySensor(
            coordinator=coordinator,
            server_uuid="test-uuid",
            server_name="test-server",
        )

        assert sensor.is_on is True

    def test_array_started_sensor_is_off_when_stopped(self) -> None:
        """Test array started sensor is OFF when array is stopped."""
        coordinator = MagicMock(spec=UnraidStorageCoordinator)
        coordinator.data = make_storage_data(array_state="STOPPED")

        sensor = ArrayStartedBinarySensor(
            coordinator=coordinator,
            server_uuid="test-uuid",
            server_name="test-server",
        )

        assert sensor.is_on is False


class TestParityCheckRunningBinarySensor:
    """Test Parity Check Running binary sensor."""

    def test_parity_check_running_sensor_creation(self) -> None:
        """Test parity check running sensor creation."""
        coordinator = MagicMock(spec=UnraidStorageCoordinator)
        coordinator.data = make_storage_data(
            parity_status=ParityCheck(status="RUNNING", progress=50, errors=0)
        )

        sensor = ParityCheckRunningBinarySensor(
            coordinator=coordinator,
            server_uuid="test-uuid",
            server_name="test-server",
        )

        assert sensor.unique_id == "test-uuid_parity_check_running"
        assert sensor.name == "Parity Check Running"

    def test_parity_check_running_when_running(self) -> None:
        """Test parity check running sensor is ON when parity check is running."""
        coordinator = MagicMock(spec=UnraidStorageCoordinator)
        coordinator.data = make_storage_data(
            parity_status=ParityCheck(status="RUNNING", progress=50, errors=0)
        )

        sensor = ParityCheckRunningBinarySensor(
            coordinator=coordinator,
            server_uuid="test-uuid",
            server_name="test-server",
        )

        assert sensor.is_on is True

    def test_parity_check_running_when_paused(self) -> None:
        """Test parity check running sensor is ON when paused."""
        coordinator = MagicMock(spec=UnraidStorageCoordinator)
        coordinator.data = make_storage_data(
            parity_status=ParityCheck(status="PAUSED", progress=50, errors=0)
        )

        sensor = ParityCheckRunningBinarySensor(
            coordinator=coordinator,
            server_uuid="test-uuid",
            server_name="test-server",
        )

        assert sensor.is_on is True

    def test_parity_check_not_running_when_completed(self) -> None:
        """Test parity check running sensor is OFF when completed."""
        coordinator = MagicMock(spec=UnraidStorageCoordinator)
        coordinator.data = make_storage_data(
            parity_status=ParityCheck(status="COMPLETED", progress=100, errors=0)
        )

        sensor = ParityCheckRunningBinarySensor(
            coordinator=coordinator,
            server_uuid="test-uuid",
            server_name="test-server",
        )

        assert sensor.is_on is False


class TestParityValidBinarySensor:
    """Test Parity Valid binary sensor."""

    def test_parity_valid_sensor_creation(self) -> None:
        """Test parity valid sensor creation."""
        coordinator = MagicMock(spec=UnraidStorageCoordinator)
        coordinator.data = make_storage_data(
            parity_status=ParityCheck(status="COMPLETED", progress=100, errors=0)
        )

        sensor = ParityValidBinarySensor(
            coordinator=coordinator,
            server_uuid="test-uuid",
            server_name="test-server",
        )

        assert sensor.unique_id == "test-uuid_parity_valid"
        assert sensor.name == "Parity Valid"

    def test_parity_valid_no_problem_when_completed(self) -> None:
        """Test parity valid sensor is OFF (no problem) when completed successfully."""
        coordinator = MagicMock(spec=UnraidStorageCoordinator)
        coordinator.data = make_storage_data(
            parity_status=ParityCheck(status="COMPLETED", progress=100, errors=0)
        )

        sensor = ParityValidBinarySensor(
            coordinator=coordinator,
            server_uuid="test-uuid",
            server_name="test-server",
        )

        assert sensor.is_on is False

    def test_parity_valid_problem_when_failed(self) -> None:
        """Test parity valid sensor is ON (problem) when failed."""
        coordinator = MagicMock(spec=UnraidStorageCoordinator)
        coordinator.data = make_storage_data(
            parity_status=ParityCheck(status="FAILED", progress=100, errors=0)
        )

        sensor = ParityValidBinarySensor(
            coordinator=coordinator,
            server_uuid="test-uuid",
            server_name="test-server",
        )

        assert sensor.is_on is True

    def test_parity_valid_problem_when_errors(self) -> None:
        """Test parity valid sensor is ON (problem) when errors exist."""
        coordinator = MagicMock(spec=UnraidStorageCoordinator)
        coordinator.data = make_storage_data(
            parity_status=ParityCheck(status="COMPLETED", progress=100, errors=5)
        )

        sensor = ParityValidBinarySensor(
            coordinator=coordinator,
            server_uuid="test-uuid",
            server_name="test-server",
        )

        assert sensor.is_on is True


class TestUPSBatterySensor:
    """Tests for UPS battery sensor."""

    def test_ups_battery_sensor_creation(self) -> None:
        """Test UPS battery sensor entity creation."""
        ups = UPSDevice(
            id="ups:1",
            name="APC",
            status="Online",
            battery=UPSBattery(charge_level=95, estimated_runtime=1200),
            power=UPSPower(
                input_voltage=120.0, output_voltage=118.5, load_percentage=20.5
            ),
        )
        coordinator = MagicMock(spec=UnraidSystemCoordinator)
        coordinator.data = make_system_data(ups_devices=[ups])

        sensor = UPSBatterySensor(
            coordinator=coordinator,
            server_uuid="test-uuid",
            server_name="test-server",
            ups=ups,
        )

        assert sensor.unique_id == "test-uuid_ups_ups:1_battery"
        assert sensor.name == "UPS Battery"
        assert sensor.device_class == SensorDeviceClass.BATTERY
        assert sensor.native_unit_of_measurement == "%"

    def test_ups_battery_sensor_state(self) -> None:
        """Test UPS battery sensor returns correct charge level."""
        ups = UPSDevice(
            id="ups:1",
            name="APC",
            status="Online",
            battery=UPSBattery(charge_level=95, estimated_runtime=1200),
            power=UPSPower(
                input_voltage=120.0, output_voltage=118.5, load_percentage=20.5
            ),
        )
        coordinator = MagicMock(spec=UnraidSystemCoordinator)
        coordinator.data = make_system_data(ups_devices=[ups])

        sensor = UPSBatterySensor(
            coordinator=coordinator,
            server_uuid="test-uuid",
            server_name="test-server",
            ups=ups,
        )

        assert sensor.native_value == 95


class TestUPSLoadSensor:
    """Tests for UPS load sensor."""

    def test_ups_load_sensor_creation(self) -> None:
        """Test UPS load sensor entity creation."""
        ups = UPSDevice(
            id="ups:1",
            name="APC",
            status="Online",
            battery=UPSBattery(charge_level=95, estimated_runtime=1200),
            power=UPSPower(
                input_voltage=120.0, output_voltage=118.5, load_percentage=20.5
            ),
        )
        coordinator = MagicMock(spec=UnraidSystemCoordinator)
        coordinator.data = make_system_data(ups_devices=[ups])

        sensor = UPSLoadSensor(
            coordinator=coordinator,
            server_uuid="test-uuid",
            server_name="test-server",
            ups=ups,
        )

        assert sensor.unique_id == "test-uuid_ups_ups:1_load"
        assert sensor.name == "UPS Load"
        assert sensor.native_unit_of_measurement == "%"

    def test_ups_load_sensor_state(self) -> None:
        """Test UPS load sensor returns correct load percentage."""
        ups = UPSDevice(
            id="ups:1",
            name="APC",
            status="Online",
            battery=UPSBattery(charge_level=95, estimated_runtime=1200),
            power=UPSPower(
                input_voltage=120.0, output_voltage=118.5, load_percentage=20.5
            ),
        )
        coordinator = MagicMock(spec=UnraidSystemCoordinator)
        coordinator.data = make_system_data(ups_devices=[ups])

        sensor = UPSLoadSensor(
            coordinator=coordinator,
            server_uuid="test-uuid",
            server_name="test-server",
            ups=ups,
        )

        assert sensor.native_value == 20.5

    def test_ups_load_sensor_attributes(self) -> None:
        """Test UPS load sensor has correct attributes."""
        ups = UPSDevice(
            id="ups:1",
            name="APC",
            status="Online",
            battery=UPSBattery(charge_level=95, estimated_runtime=1200),
            power=UPSPower(
                input_voltage=120.0, output_voltage=118.5, load_percentage=20.5
            ),
        )
        coordinator = MagicMock(spec=UnraidSystemCoordinator)
        coordinator.data = make_system_data(ups_devices=[ups])

        sensor = UPSLoadSensor(
            coordinator=coordinator,
            server_uuid="test-uuid",
            server_name="test-server",
            ups=ups,
        )

        attrs = sensor.extra_state_attributes
        assert attrs["model"] == "APC"
        assert attrs["status"] == "Online"
        assert attrs["input_voltage"] == 120.0
        assert attrs["output_voltage"] == 118.5


class TestUPSRuntimeSensor:
    """Tests for UPS runtime sensor."""

    def test_ups_runtime_sensor_creation(self) -> None:
        """Test UPS runtime sensor entity creation."""
        ups = UPSDevice(
            id="ups:1",
            name="APC",
            status="Online",
            battery=UPSBattery(charge_level=95, estimated_runtime=1200),
            power=UPSPower(
                input_voltage=120.0, output_voltage=118.5, load_percentage=20.5
            ),
        )
        coordinator = MagicMock(spec=UnraidSystemCoordinator)
        coordinator.data = make_system_data(ups_devices=[ups])

        sensor = UPSRuntimeSensor(
            coordinator=coordinator,
            server_uuid="test-uuid",
            server_name="test-server",
            ups=ups,
        )

        assert sensor.unique_id == "test-uuid_ups_ups:1_runtime"
        assert sensor.name == "UPS Runtime"

    def test_ups_runtime_sensor_state(self) -> None:
        """Test UPS runtime sensor returns human-readable duration."""
        ups = UPSDevice(
            id="ups:1",
            name="APC",
            status="Online",
            battery=UPSBattery(charge_level=95, estimated_runtime=3660),  # 1h 1m
            power=UPSPower(
                input_voltage=120.0, output_voltage=118.5, load_percentage=20.5
            ),
        )
        coordinator = MagicMock(spec=UnraidSystemCoordinator)
        coordinator.data = make_system_data(ups_devices=[ups])

        sensor = UPSRuntimeSensor(
            coordinator=coordinator,
            server_uuid="test-uuid",
            server_name="test-server",
            ups=ups,
        )

        assert sensor.native_value == "1 hour 1 minute"


class TestUPSPowerSensor:
    """Tests for UPS power consumption sensor."""

    def test_ups_power_sensor_creation(self) -> None:
        """Test UPS power sensor entity creation."""

        ups = UPSDevice(
            id="ups:1",
            name="APC",
            status="Online",
            battery=UPSBattery(charge_level=95, estimated_runtime=1200),
            power=UPSPower(
                input_voltage=120.0, output_voltage=118.5, load_percentage=20.5
            ),
        )
        coordinator = MagicMock(spec=UnraidSystemCoordinator)
        coordinator.data = make_system_data(ups_devices=[ups])

        sensor = UPSPowerSensor(
            coordinator=coordinator,
            server_uuid="test-uuid",
            server_name="test-server",
            ups=ups,
            ups_capacity_va=1000,
            ups_nominal_power=800,
        )

        assert sensor.unique_id == "test-uuid_ups_ups:1_power"
        assert sensor.name == "UPS Power"
        assert sensor.device_class == SensorDeviceClass.POWER
        assert sensor.native_unit_of_measurement == UnitOfPower.WATT
        assert sensor.state_class == SensorStateClass.MEASUREMENT

    def test_ups_power_sensor_calculates_power(self) -> None:
        """Test UPS power sensor calculates power from load and nominal power."""
        # Load: 20.5%, Nominal Power: 800W
        # Expected: 20.5 / 100 * 800 = 164W
        ups = UPSDevice(
            id="ups:1",
            name="APC",
            status="Online",
            battery=UPSBattery(charge_level=95, estimated_runtime=1200),
            power=UPSPower(
                input_voltage=120.0, output_voltage=118.5, load_percentage=20.5
            ),
        )
        coordinator = MagicMock(spec=UnraidSystemCoordinator)
        coordinator.data = make_system_data(ups_devices=[ups])

        sensor = UPSPowerSensor(
            coordinator=coordinator,
            server_uuid="test-uuid",
            server_name="test-server",
            ups=ups,
            ups_capacity_va=1000,
            ups_nominal_power=800,
        )

        assert sensor.native_value == 164.0

    def test_ups_power_sensor_unavailable_when_nominal_power_zero(self) -> None:
        """Test UPS power sensor is unavailable when nominal power is 0."""
        ups = UPSDevice(
            id="ups:1",
            name="APC",
            status="Online",
            battery=UPSBattery(charge_level=95, estimated_runtime=1200),
            power=UPSPower(
                input_voltage=120.0, output_voltage=118.5, load_percentage=20.5
            ),
        )
        coordinator = MagicMock(spec=UnraidSystemCoordinator)
        coordinator.data = make_system_data(ups_devices=[ups])
        coordinator.last_update_success = True

        sensor = UPSPowerSensor(
            coordinator=coordinator,
            server_uuid="test-uuid",
            server_name="test-server",
            ups=ups,
            ups_capacity_va=1000,
            ups_nominal_power=0,
        )

        assert sensor.available is False
        assert sensor.native_value is None

    def test_ups_power_sensor_attributes(self) -> None:
        """Test UPS power sensor has correct attributes."""
        ups = UPSDevice(
            id="ups:1",
            name="APC",
            status="Online",
            battery=UPSBattery(charge_level=95, estimated_runtime=1200),
            power=UPSPower(
                input_voltage=120.0, output_voltage=118.5, load_percentage=20.5
            ),
        )
        coordinator = MagicMock(spec=UnraidSystemCoordinator)
        coordinator.data = make_system_data(ups_devices=[ups])

        sensor = UPSPowerSensor(
            coordinator=coordinator,
            server_uuid="test-uuid",
            server_name="test-server",
            ups=ups,
            ups_capacity_va=1000,
            ups_nominal_power=800,
        )

        attrs = sensor.extra_state_attributes
        assert attrs["model"] == "APC"
        assert attrs["status"] == "Online"
        assert attrs["ups_capacity_va"] == 1000
        assert attrs["nominal_power_watts"] == 800
        assert attrs["load_percentage"] == 20.5
        assert attrs["input_voltage"] == 120.0
        assert attrs["output_voltage"] == 118.5

    def test_ups_power_sensor_real_world_example(self) -> None:
        """Test UPS power sensor with real-world values from API."""
        # Based on actual UPS data: PR1000ELCDRT1U (1000VA, 800W nominal), 12% load
        # Expected: 12 / 100 * 800 = 96W (matches Unraid UI)
        ups = UPSDevice(
            id="PR1000ELCDRT1U",
            name="PR1000ELCDRT1U",
            status="ONLINE",
            battery=UPSBattery(charge_level=100, estimated_runtime=6360),
            power=UPSPower(
                input_voltage=236.0, output_voltage=236.0, load_percentage=12.0
            ),
        )
        coordinator = MagicMock(spec=UnraidSystemCoordinator)
        coordinator.data = make_system_data(ups_devices=[ups])

        sensor = UPSPowerSensor(
            coordinator=coordinator,
            server_uuid="test-uuid",
            server_name="test-server",
            ups=ups,
            ups_capacity_va=1000,
            ups_nominal_power=800,
        )

        assert sensor.native_value == 96.0


class TestAsyncSetupEntry:
    """Test async_setup_entry function."""

    @pytest.mark.asyncio
    async def test_setup_entry_creates_system_sensors(self, hass) -> None:
        """Test setup creates system sensors."""

        system_coordinator = MagicMock(spec=UnraidSystemCoordinator)
        system_coordinator.data = make_system_data()

        storage_coordinator = MagicMock(spec=UnraidStorageCoordinator)
        storage_coordinator.data = make_storage_data()

        mock_entry = MagicMock()
        mock_entry.data = {"host": "192.168.1.100"}
        mock_entry.options = {}
        mock_entry.runtime_data = UnraidRuntimeData(
            api_client=MagicMock(),
            system_coordinator=system_coordinator,
            storage_coordinator=storage_coordinator,
            server_info={
                "uuid": "test-uuid",
                "name": "tower",
                "manufacturer": "Supermicro",
                "model": "X11",
            },
        )

        added_entities = []

        def mock_add_entities(entities) -> None:
            added_entities.extend(entities)

        await async_setup_entry(hass, mock_entry, mock_add_entities)

        # Should create system sensors (CPU, RAM, Temp, Uptime, etc.)
        assert len(added_entities) > 0

        # Check some expected sensor types exist

        entity_types = {type(e).__name__ for e in added_entities}
        assert "CpuSensor" in entity_types
        assert "RAMUsageSensor" in entity_types
        assert "ArrayStateSensor" in entity_types

    @pytest.mark.asyncio
    async def test_setup_entry_creates_ups_sensors(self, hass) -> None:
        """Test setup creates UPS sensors when UPS devices exist."""

        ups = UPSDevice(
            id="ups:1",
            name="APC",
            status="Online",
            battery=UPSBattery(charge_level=100),
            power=UPSPower(load_percentage=20.0),
        )

        system_coordinator = MagicMock(spec=UnraidSystemCoordinator)
        system_coordinator.data = make_system_data(ups_devices=[ups])

        storage_coordinator = MagicMock(spec=UnraidStorageCoordinator)
        storage_coordinator.data = make_storage_data()

        mock_entry = MagicMock()
        mock_entry.data = {"host": "192.168.1.100"}
        mock_entry.options = {"ups_capacity_va": 1000}
        mock_entry.runtime_data = UnraidRuntimeData(
            api_client=MagicMock(),
            system_coordinator=system_coordinator,
            storage_coordinator=storage_coordinator,
            server_info={"uuid": "test-uuid", "name": "tower"},
        )

        added_entities = []

        def mock_add_entities(entities) -> None:
            added_entities.extend(entities)

        await async_setup_entry(hass, mock_entry, mock_add_entities)

        entity_types = {type(e).__name__ for e in added_entities}
        assert "UPSBatterySensor" in entity_types
        assert "UPSLoadSensor" in entity_types
        assert "UPSRuntimeSensor" in entity_types
        assert "UPSPowerSensor" in entity_types

    @pytest.mark.asyncio
    async def test_setup_entry_creates_disk_sensors(self, hass) -> None:
        """Test setup creates disk sensors for disks in storage data."""

        disk = ArrayDisk(id="disk:1", name="Disk 1", status="DISK_OK")

        system_coordinator = MagicMock(spec=UnraidSystemCoordinator)
        system_coordinator.data = make_system_data()

        storage_coordinator = MagicMock(spec=UnraidStorageCoordinator)
        storage_coordinator.data = make_storage_data(disks=[disk])

        mock_entry = MagicMock()
        mock_entry.data = {"host": "192.168.1.100"}
        mock_entry.options = {}
        mock_entry.runtime_data = UnraidRuntimeData(
            api_client=MagicMock(),
            system_coordinator=system_coordinator,
            storage_coordinator=storage_coordinator,
            server_info={"uuid": "test-uuid", "name": "tower"},
        )

        added_entities = []

        def mock_add_entities(entities) -> None:
            added_entities.extend(entities)

        await async_setup_entry(hass, mock_entry, mock_add_entities)

        entity_types = {type(e).__name__ for e in added_entities}
        assert "DiskUsageSensor" in entity_types

    @pytest.mark.asyncio
    async def test_setup_entry_no_storage_data(self, hass) -> None:
        """Test setup handles None storage data."""

        system_coordinator = MagicMock(spec=UnraidSystemCoordinator)
        system_coordinator.data = make_system_data()

        storage_coordinator = MagicMock(spec=UnraidStorageCoordinator)
        storage_coordinator.data = None

        mock_entry = MagicMock()
        mock_entry.data = {"host": "192.168.1.100"}
        mock_entry.options = {}
        mock_entry.runtime_data = UnraidRuntimeData(
            api_client=MagicMock(),
            system_coordinator=system_coordinator,
            storage_coordinator=storage_coordinator,
            server_info={"uuid": "test-uuid", "name": "tower"},
        )

        added_entities = []

        def mock_add_entities(entities) -> None:
            added_entities.extend(entities)

        # Should not raise, just skip disk/share sensors
        await async_setup_entry(hass, mock_entry, mock_add_entities)

        # Should still create system sensors
        assert len(added_entities) > 0


# =============================================================================
# Additional Coverage Tests
# =============================================================================


class TestCpuPowerSensor:
    """Test CPU power sensor."""

    def test_cpu_power_sensor_creation(self) -> None:
        """Test CPU power sensor creation with proper attributes."""
        coordinator = MagicMock(spec=UnraidSystemCoordinator)
        coordinator.data = make_system_data(cpu_power=65.5)

        sensor = CpuPowerSensor(
            coordinator=coordinator,
            server_uuid="test-uuid",
            server_name="test-server",
        )

        assert sensor.unique_id == "test-uuid_cpu_power"
        assert sensor.name == "CPU Power"
        assert sensor.device_class == SensorDeviceClass.POWER
        assert sensor.state_class == SensorStateClass.MEASUREMENT

    def test_cpu_power_sensor_state(self) -> None:
        """Test CPU power sensor returns correct power value."""
        coordinator = MagicMock(spec=UnraidSystemCoordinator)
        coordinator.data = make_system_data(cpu_power=85.5)

        sensor = CpuPowerSensor(
            coordinator=coordinator,
            server_uuid="test-uuid",
            server_name="test-server",
        )

        assert sensor.native_value == 85.5


class TestActiveNotificationsSensor:
    """Test active notifications sensor."""

    def test_active_notifications_sensor_creation(self) -> None:
        """Test active notifications sensor creation."""
        coordinator = MagicMock(spec=UnraidSystemCoordinator)
        coordinator.data = make_system_data(notifications_unread=5)

        sensor = ActiveNotificationsSensor(
            coordinator=coordinator,
            server_uuid="test-uuid",
            server_name="test-server",
        )

        assert sensor.unique_id == "test-uuid_active_notifications"
        assert sensor.name == "Active Notifications"
        assert sensor.entity_category == EntityCategory.DIAGNOSTIC
        assert sensor.state_class == SensorStateClass.MEASUREMENT
        assert sensor.native_unit_of_measurement == "notifications"

    def test_active_notifications_sensor_state(self) -> None:
        """Test active notifications sensor returns correct count."""
        coordinator = MagicMock(spec=UnraidSystemCoordinator)
        coordinator.data = make_system_data(notifications_unread=3)

        sensor = ActiveNotificationsSensor(
            coordinator=coordinator,
            server_uuid="test-uuid",
            server_name="test-server",
        )

        assert sensor.native_value == 3


class TestDiskUsageSensorAttributes:
    """Test disk usage sensor extra state attributes edge cases."""

    def test_disk_usage_attributes_with_fstype(self) -> None:
        """Test disk usage sensor includes filesystem type when available."""
        disk = ArrayDisk(
            id="disk1",
            name="Disk 1",
            fs_type="xfs",
            fs_size=1000,
            fs_used=500,
            fs_free=500,
        )
        coordinator = MagicMock(spec=UnraidStorageCoordinator)
        coordinator.data = make_storage_data(disks=[disk])

        sensor = DiskUsageSensor(
            coordinator=coordinator,
            server_uuid="test-uuid",
            server_name="test-server",
            disk=disk,
        )

        attrs = sensor.extra_state_attributes
        assert attrs.get("filesystem") == "xfs"

    def test_disk_usage_attributes_spinning_false(self) -> None:
        """Test disk usage sensor shows standby when not spinning."""
        disk = ArrayDisk(
            id="disk1",
            name="Disk 1",
            is_spinning=False,
            fs_size=1000,
            fs_used=500,
            fs_free=500,
        )
        coordinator = MagicMock(spec=UnraidStorageCoordinator)
        coordinator.data = make_storage_data(disks=[disk])

        sensor = DiskUsageSensor(
            coordinator=coordinator,
            server_uuid="test-uuid",
            server_name="test-server",
            disk=disk,
        )

        attrs = sensor.extra_state_attributes
        assert attrs.get("spin_state") == "standby"

    def test_disk_usage_attributes_smart_status(self) -> None:
        """Test disk usage sensor includes SMART status when available."""
        disk = ArrayDisk(
            id="disk1",
            name="Disk 1",
            smart_status="PASSED",
            fs_size=1000,
            fs_used=500,
            fs_free=500,
        )
        coordinator = MagicMock(spec=UnraidStorageCoordinator)
        coordinator.data = make_storage_data(disks=[disk])

        sensor = DiskUsageSensor(
            coordinator=coordinator,
            server_uuid="test-uuid",
            server_name="test-server",
            disk=disk,
        )

        attrs = sensor.extra_state_attributes
        assert attrs.get("smart_status") == "PASSED"


class TestUPSRuntimeEdgeCases:
    """Test UPS runtime sensor edge cases."""

    def test_ups_runtime_minutes_only(self) -> None:
        """Test UPS runtime with only minutes (no hours)."""
        ups = UPSDevice(
            id="ups:1",
            name="APC",
            battery=UPSBattery(estimated_runtime=1800),  # 30 minutes
        )
        coordinator = MagicMock(spec=UnraidSystemCoordinator)
        coordinator.data = make_system_data(ups_devices=[ups])

        sensor = UPSRuntimeSensor(
            coordinator=coordinator,
            server_uuid="test-uuid",
            server_name="test-server",
            ups=ups,
        )

        assert sensor.native_value == "30 minutes"

    def test_ups_runtime_singular_units(self) -> None:
        """Test UPS runtime with singular minute."""
        ups = UPSDevice(
            id="ups:1",
            name="APC",
            battery=UPSBattery(estimated_runtime=60),  # 1 minute
        )
        coordinator = MagicMock(spec=UnraidSystemCoordinator)
        coordinator.data = make_system_data(ups_devices=[ups])

        sensor = UPSRuntimeSensor(
            coordinator=coordinator,
            server_uuid="test-uuid",
            server_name="test-server",
            ups=ups,
        )

        assert sensor.native_value == "1 minute"

    def test_ups_runtime_1_hour_1_minute(self) -> None:
        """Test UPS runtime with singular hour and minute."""
        ups = UPSDevice(
            id="ups:1",
            name="APC",
            battery=UPSBattery(estimated_runtime=3660),  # 1 hour 1 minute
        )
        coordinator = MagicMock(spec=UnraidSystemCoordinator)
        coordinator.data = make_system_data(ups_devices=[ups])

        sensor = UPSRuntimeSensor(
            coordinator=coordinator,
            server_uuid="test-uuid",
            server_name="test-server",
            ups=ups,
        )

        assert sensor.native_value == "1 hour 1 minute"

    def test_ups_runtime_attributes_with_runtime(self) -> None:
        """Test UPS runtime sensor attributes include runtime info."""
        ups = UPSDevice(
            id="ups:1",
            name="APC",
            status="Online",
            battery=UPSBattery(estimated_runtime=1800),
        )
        coordinator = MagicMock(spec=UnraidSystemCoordinator)
        coordinator.data = make_system_data(ups_devices=[ups])

        sensor = UPSRuntimeSensor(
            coordinator=coordinator,
            server_uuid="test-uuid",
            server_name="test-server",
            ups=ups,
        )

        attrs = sensor.extra_state_attributes
        assert attrs["runtime_seconds"] == 1800
        assert attrs["runtime_minutes"] == 30


class TestShareUsageSensor:
    """Test share usage sensor."""

    def test_share_usage_sensor_creation(self) -> None:
        """Test share usage sensor creation."""
        share = Share(
            id="share:1", name="appdata", size=1000000, used=500000, free=500000
        )
        coordinator = MagicMock(spec=UnraidStorageCoordinator)
        coordinator.data = make_storage_data(shares=[share])

        sensor = ShareUsageSensor(
            coordinator=coordinator,
            server_uuid="test-uuid",
            server_name="test-server",
            share=share,
        )

        assert sensor.unique_id == "test-uuid_share_share:1_usage"
        assert sensor.name == "Share appdata Usage"
        assert sensor.state_class == SensorStateClass.MEASUREMENT
        assert sensor.native_unit_of_measurement == "%"

    def test_share_usage_sensor_state(self) -> None:
        """Test share usage sensor returns correct percentage."""
        share = Share(id="share:1", name="appdata", size=1000, used=500, free=500)
        coordinator = MagicMock(spec=UnraidStorageCoordinator)
        coordinator.data = make_storage_data(shares=[share])

        sensor = ShareUsageSensor(
            coordinator=coordinator,
            server_uuid="test-uuid",
            server_name="test-server",
            share=share,
        )

        assert sensor.native_value == 50.0

    def test_share_usage_sensor_missing_share(self) -> None:
        """Test share usage sensor returns None when share not found."""
        share = Share(id="share_missing", name="missing")
        coordinator = MagicMock(spec=UnraidStorageCoordinator)
        coordinator.data = make_storage_data(shares=[])

        sensor = ShareUsageSensor(
            coordinator=coordinator,
            server_uuid="test-uuid",
            server_name="test-server",
            share=share,
        )

        assert sensor.native_value is None
        assert sensor.extra_state_attributes == {}

    def test_share_usage_sensor_attributes(self) -> None:
        """Test share usage sensor returns human-readable attributes."""
        share = Share(
            id="share:1",
            name="appdata",
            size=1073741824,
            used=536870912,
            free=536870912,
        )
        coordinator = MagicMock(spec=UnraidStorageCoordinator)
        coordinator.data = make_storage_data(shares=[share])

        sensor = ShareUsageSensor(
            coordinator=coordinator,
            server_uuid="test-uuid",
            server_name="test-server",
            share=share,
        )

        attrs = sensor.extra_state_attributes
        assert "total" in attrs
        assert "used" in attrs
        assert "free" in attrs


class TestFlashUsageSensor:
    """Test flash/boot device usage sensor."""

    def test_flash_usage_sensor_creation(self) -> None:
        """Test flash usage sensor creation."""
        boot = ArrayDisk(
            id="boot", name="Flash", fs_size=16000000, fs_used=8000000, fs_free=8000000
        )
        coordinator = MagicMock(spec=UnraidStorageCoordinator)
        coordinator.data = make_storage_data(boot=boot)

        sensor = FlashUsageSensor(
            coordinator=coordinator,
            server_uuid="test-uuid",
            server_name="test-server",
        )

        assert sensor.unique_id == "test-uuid_flash_usage"
        assert sensor.name == "Flash Device Usage"
        assert sensor.state_class == SensorStateClass.MEASUREMENT
        assert sensor.native_unit_of_measurement == "%"

    def test_flash_usage_sensor_state(self) -> None:
        """Test flash usage sensor returns correct percentage."""
        boot = ArrayDisk(
            id="boot", name="Flash", fs_size=16000, fs_used=8000, fs_free=8000
        )
        coordinator = MagicMock(spec=UnraidStorageCoordinator)
        coordinator.data = make_storage_data(boot=boot)

        sensor = FlashUsageSensor(
            coordinator=coordinator,
            server_uuid="test-uuid",
            server_name="test-server",
        )

        assert sensor.native_value == 50.0

    def test_flash_usage_sensor_none_boot(self) -> None:
        """Test flash usage sensor returns None when boot is None."""
        coordinator = MagicMock(spec=UnraidStorageCoordinator)
        coordinator.data = make_storage_data(boot=None)

        sensor = FlashUsageSensor(
            coordinator=coordinator,
            server_uuid="test-uuid",
            server_name="test-server",
        )

        assert sensor.native_value is None
        assert sensor.extra_state_attributes == {}

    def test_flash_usage_sensor_attributes(self) -> None:
        """Test flash usage sensor returns correct attributes."""
        boot = ArrayDisk(
            id="boot",
            name="Flash",
            device="sdc",
            status="DISK_OK",
            fs_size=16000000,
            fs_used=8000000,
            fs_free=8000000,
        )
        coordinator = MagicMock(spec=UnraidStorageCoordinator)
        coordinator.data = make_storage_data(boot=boot)

        sensor = FlashUsageSensor(
            coordinator=coordinator,
            server_uuid="test-uuid",
            server_name="test-server",
        )

        attrs = sensor.extra_state_attributes
        assert "total" in attrs
        assert "used" in attrs
        assert "free" in attrs
        assert attrs["device"] == "sdc"
        assert attrs["status"] == "DISK_OK"


class TestSetupEntryEdgeCases:
    """Test async_setup_entry edge cases."""

    @pytest.mark.asyncio
    async def test_setup_entry_creates_share_sensors(self, hass) -> None:
        """Test setup creates share sensors for shares in storage data."""

        share = Share(id="share:1", name="appdata", size=1000, used=500, free=500)

        system_coordinator = MagicMock(spec=UnraidSystemCoordinator)
        system_coordinator.data = make_system_data()

        storage_coordinator = MagicMock(spec=UnraidStorageCoordinator)
        storage_coordinator.data = make_storage_data(shares=[share])

        mock_entry = MagicMock()
        mock_entry.data = {"host": "192.168.1.100"}
        mock_entry.options = {}
        mock_entry.runtime_data = UnraidRuntimeData(
            api_client=MagicMock(),
            system_coordinator=system_coordinator,
            storage_coordinator=storage_coordinator,
            server_info={"uuid": "test-uuid", "name": "tower"},
        )

        added_entities = []

        def mock_add_entities(entities) -> None:
            added_entities.extend(entities)

        await async_setup_entry(hass, mock_entry, mock_add_entities)

        entity_types = {type(e).__name__ for e in added_entities}
        assert "ShareUsageSensor" in entity_types

    @pytest.mark.asyncio
    async def test_setup_entry_creates_flash_sensor(self, hass) -> None:
        """Test setup creates flash sensor when boot device exists."""

        boot = ArrayDisk(id="boot", name="Flash", fs_size=16000, fs_used=8000)

        system_coordinator = MagicMock(spec=UnraidSystemCoordinator)
        system_coordinator.data = make_system_data()

        storage_coordinator = MagicMock(spec=UnraidStorageCoordinator)
        storage_coordinator.data = make_storage_data(boot=boot)

        mock_entry = MagicMock()
        mock_entry.data = {"host": "192.168.1.100"}
        mock_entry.options = {}
        mock_entry.runtime_data = UnraidRuntimeData(
            api_client=MagicMock(),
            system_coordinator=system_coordinator,
            storage_coordinator=storage_coordinator,
            server_info={"uuid": "test-uuid", "name": "tower"},
        )

        added_entities = []

        def mock_add_entities(entities) -> None:
            added_entities.extend(entities)

        await async_setup_entry(hass, mock_entry, mock_add_entities)

        entity_types = {type(e).__name__ for e in added_entities}
        assert "FlashUsageSensor" in entity_types

    @pytest.mark.asyncio
    async def test_setup_entry_creates_cache_disk_sensors(self, hass) -> None:
        """Test setup creates disk usage sensors for cache disks."""

        cache_disk = ArrayDisk(id="cache:1", name="Cache", type="CACHE")

        system_coordinator = MagicMock(spec=UnraidSystemCoordinator)
        system_coordinator.data = make_system_data()

        storage_coordinator = MagicMock(spec=UnraidStorageCoordinator)
        storage_coordinator.data = make_storage_data(caches=[cache_disk])

        mock_entry = MagicMock()
        mock_entry.data = {"host": "192.168.1.100"}
        mock_entry.options = {}
        mock_entry.runtime_data = UnraidRuntimeData(
            api_client=MagicMock(),
            system_coordinator=system_coordinator,
            storage_coordinator=storage_coordinator,
            server_info={"uuid": "test-uuid", "name": "tower"},
        )

        added_entities = []

        def mock_add_entities(entities) -> None:
            added_entities.extend(entities)

        await async_setup_entry(hass, mock_entry, mock_add_entities)

        # Find the DiskUsageSensor for the cache disk
        cache_sensors = [
            e
            for e in added_entities
            if isinstance(e, DiskUsageSensor) and "cache:1" in e.unique_id
        ]
        assert len(cache_sensors) == 1

    @pytest.mark.asyncio
    async def test_setup_entry_no_ups_sensors_when_no_ups(self, hass) -> None:
        """Test setup doesn't create UPS sensors when no UPS devices."""

        system_coordinator = MagicMock(spec=UnraidSystemCoordinator)
        system_coordinator.data = make_system_data(ups_devices=[])

        storage_coordinator = MagicMock(spec=UnraidStorageCoordinator)
        storage_coordinator.data = make_storage_data()

        mock_entry = MagicMock()
        mock_entry.data = {"host": "192.168.1.100"}
        mock_entry.options = {}
        mock_entry.runtime_data = UnraidRuntimeData(
            api_client=MagicMock(),
            system_coordinator=system_coordinator,
            storage_coordinator=storage_coordinator,
            server_info={"uuid": "test-uuid", "name": "tower"},
        )

        added_entities = []

        def mock_add_entities(entities) -> None:
            added_entities.extend(entities)

        await async_setup_entry(hass, mock_entry, mock_add_entities)

        entity_types = {type(e).__name__ for e in added_entities}
        assert "UPSBatterySensor" not in entity_types

    @pytest.mark.asyncio
    async def test_setup_entry_uses_ups_capacity_from_options(self, hass) -> None:
        """Test setup uses UPS capacity from entry options."""

        ups = UPSDevice(
            id="ups:1",
            name="APC",
            battery=UPSBattery(charge_level=95),
            power=UPSPower(load_percentage=20.0),
        )

        system_coordinator = MagicMock(spec=UnraidSystemCoordinator)
        system_coordinator.data = make_system_data(ups_devices=[ups])

        storage_coordinator = MagicMock(spec=UnraidStorageCoordinator)
        storage_coordinator.data = make_storage_data()

        mock_entry = MagicMock()
        mock_entry.data = {"host": "192.168.1.100"}
        mock_entry.options = {CONF_UPS_CAPACITY_VA: 1500, CONF_UPS_NOMINAL_POWER: 1200}
        mock_entry.runtime_data = UnraidRuntimeData(
            api_client=MagicMock(),
            system_coordinator=system_coordinator,
            storage_coordinator=storage_coordinator,
            server_info={"uuid": "test-uuid", "name": "tower"},
        )

        added_entities = []

        def mock_add_entities(entities) -> None:
            added_entities.extend(entities)

        await async_setup_entry(hass, mock_entry, mock_add_entities)

        # Find the UPSPowerSensor and verify capacity and nominal power
        power_sensors = [e for e in added_entities if isinstance(e, UPSPowerSensor)]
        assert len(power_sensors) == 1
        assert power_sensors[0]._ups_capacity_va == 1500
        assert power_sensors[0]._ups_nominal_power == 1200
