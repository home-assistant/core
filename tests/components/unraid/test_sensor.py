"""Tests for Unraid sensor entities using entity descriptions."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

from unraid_api.models import ArrayDisk, Share, UPSBattery, UPSDevice, UPSPower

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.components.unraid.const import DOMAIN
from homeassistant.components.unraid.sensor import (
    DISK_SENSORS,
    SHARE_SENSORS,
    STORAGE_SENSORS,
    SYSTEM_SENSORS,
    UPS_SENSORS,
    UnraidDiskSensorEntity,
    UnraidShareSensorEntity,
    UnraidSystemSensorEntity,
    UnraidUPSPowerSensorEntity,
    UnraidUPSSensorEntity,
    _format_duration,
    _parse_uptime,
)
from homeassistant.const import UnitOfInformation
from homeassistant.helpers.device_registry import DeviceInfo

from .conftest import make_storage_data, make_system_data

# =============================================================================
# Helper Function Tests
# =============================================================================


class TestFormatDuration:
    """Test _format_duration helper function."""

    def test_format_duration_none(self) -> None:
        """Test _format_duration with None input."""
        assert _format_duration(None) is None

    def test_format_duration_negative(self) -> None:
        """Test _format_duration with negative input."""
        assert _format_duration(-1) is None

    def test_format_duration_zero(self) -> None:
        """Test _format_duration with zero seconds."""
        assert _format_duration(0) == "0 seconds"

    def test_format_duration_seconds_only(self) -> None:
        """Test _format_duration with seconds only."""
        assert _format_duration(45) == "45 seconds"
        assert _format_duration(1) == "1 second"

    def test_format_duration_minutes_and_seconds(self) -> None:
        """Test _format_duration with minutes and seconds."""
        assert _format_duration(90) == "1 minute, 30 seconds"
        assert _format_duration(125) == "2 minutes, 5 seconds"

    def test_format_duration_hours_minutes_seconds(self) -> None:
        """Test _format_duration with hours, minutes, seconds."""
        assert _format_duration(3661) == "1 hour, 1 minute, 1 second"
        assert _format_duration(7325) == "2 hours, 2 minutes, 5 seconds"

    def test_format_duration_days(self) -> None:
        """Test _format_duration with days."""
        assert _format_duration(86400) == "1 day"
        assert (
            _format_duration(172800 + 3600 + 60 + 1)
            == "2 days, 1 hour, 1 minute, 1 second"
        )


class TestParseUptime:
    """Test _parse_uptime helper function."""

    def test_parse_uptime_none(self) -> None:
        """Test _parse_uptime with None input."""
        assert _parse_uptime(None) is None

    def test_parse_uptime_returns_formatted_string(self) -> None:
        """Test _parse_uptime returns formatted duration string."""
        # Boot time 1 hour, 30 minutes, 45 seconds ago
        boot_time = datetime.now(UTC) - timedelta(hours=1, minutes=30, seconds=45)
        result = _parse_uptime(boot_time)
        # Should return formatted string like "1 hour, 30 minutes, 45 seconds"
        assert result is not None
        assert "hour" in result
        assert "minute" in result

    def test_parse_uptime_2_hours(self) -> None:
        """Test _parse_uptime with 2 hours ago."""
        # Boot time 2 hours ago
        boot_time = datetime.now(UTC) - timedelta(hours=2)
        result = _parse_uptime(boot_time)
        # Should return formatted string containing "2 hours"
        assert result is not None
        assert "2 hours" in result


# =============================================================================
# Entity Description Tests
# =============================================================================


class TestSystemSensorDescriptions:
    """Test system sensor entity descriptions."""

    def test_cpu_usage_sensor_description(self) -> None:
        """Test CPU usage sensor description."""
        desc = next(s for s in SYSTEM_SENSORS if s.key == "cpu_usage")
        assert desc.native_unit_of_measurement == "%"
        assert desc.state_class == SensorStateClass.MEASUREMENT
        assert desc.translation_key == "cpu_usage"

    def test_ram_usage_sensor_description(self) -> None:
        """Test RAM usage sensor description."""
        desc = next(s for s in SYSTEM_SENSORS if s.key == "ram_usage")
        assert desc.native_unit_of_measurement == "%"
        assert desc.state_class == SensorStateClass.MEASUREMENT

    def test_ram_used_sensor_description(self) -> None:
        """Test RAM used sensor description."""
        desc = next(s for s in SYSTEM_SENSORS if s.key == "ram_used")
        assert desc.device_class == SensorDeviceClass.DATA_SIZE
        assert desc.native_unit_of_measurement == UnitOfInformation.BYTES
        assert desc.suggested_unit_of_measurement == UnitOfInformation.GIBIBYTES

    def test_uptime_sensor_description(self) -> None:
        """Test uptime sensor description."""
        desc = next(s for s in SYSTEM_SENSORS if s.key == "uptime")
        # Uptime returns formatted string, no device_class or unit
        assert desc.device_class is None
        assert desc.native_unit_of_measurement is None

    def test_notifications_sensor_description(self) -> None:
        """Test notifications sensor description."""
        desc = next(s for s in SYSTEM_SENSORS if s.key == "notifications")
        assert desc.state_class == SensorStateClass.MEASUREMENT


class TestStorageSensorDescriptions:
    """Test storage sensor entity descriptions."""

    def test_array_state_sensor_description(self) -> None:
        """Test array state sensor description."""
        desc = next(s for s in STORAGE_SENSORS if s.key == "array_state")
        assert desc.translation_key == "array_state"

    def test_array_usage_sensor_description(self) -> None:
        """Test array usage sensor description."""
        desc = next(s for s in STORAGE_SENSORS if s.key == "array_usage")
        assert desc.native_unit_of_measurement == "%"
        assert desc.state_class == SensorStateClass.MEASUREMENT

    def test_array_used_sensor_description(self) -> None:
        """Test array used sensor description."""
        desc = next(s for s in STORAGE_SENSORS if s.key == "array_used")
        assert desc.device_class == SensorDeviceClass.DATA_SIZE
        assert desc.native_unit_of_measurement == UnitOfInformation.KIBIBYTES
        assert desc.suggested_unit_of_measurement == UnitOfInformation.TEBIBYTES

    def test_parity_progress_sensor_description(self) -> None:
        """Test parity progress sensor description."""
        desc = next(s for s in STORAGE_SENSORS if s.key == "parity_progress")
        assert desc.native_unit_of_measurement == "%"


class TestDiskSensorDescriptions:
    """Test disk sensor entity descriptions."""

    def test_disk_usage_sensor_description(self) -> None:
        """Test disk usage sensor description."""
        desc = next(s for s in DISK_SENSORS if s.key == "usage")
        assert desc.native_unit_of_measurement == "%"
        assert desc.translation_key == "disk_usage"

    def test_disk_used_sensor_description(self) -> None:
        """Test disk used sensor description."""
        desc = next(s for s in DISK_SENSORS if s.key == "used")
        assert desc.device_class == SensorDeviceClass.DATA_SIZE
        assert desc.native_unit_of_measurement == UnitOfInformation.KIBIBYTES

    def test_disk_temp_sensor_description(self) -> None:
        """Test disk temperature sensor description."""
        desc = next(s for s in DISK_SENSORS if s.key == "temp")
        assert desc.device_class == SensorDeviceClass.TEMPERATURE


class TestShareSensorDescriptions:
    """Test share sensor entity descriptions."""

    def test_share_usage_sensor_description(self) -> None:
        """Test share usage sensor description."""
        desc = next(s for s in SHARE_SENSORS if s.key == "usage")
        assert desc.native_unit_of_measurement == "%"
        assert desc.translation_key == "share_usage"


class TestUPSSensorDescriptions:
    """Test UPS sensor entity descriptions."""

    def test_ups_battery_sensor_description(self) -> None:
        """Test UPS battery sensor description."""
        desc = next(s for s in UPS_SENSORS if s.key == "battery")
        assert desc.device_class == SensorDeviceClass.BATTERY
        assert desc.native_unit_of_measurement == "%"

    def test_ups_load_sensor_description(self) -> None:
        """Test UPS load sensor description."""
        desc = next(s for s in UPS_SENSORS if s.key == "load")
        assert desc.native_unit_of_measurement == "%"

    def test_ups_runtime_sensor_description(self) -> None:
        """Test UPS runtime sensor description."""
        desc = next(s for s in UPS_SENSORS if s.key == "runtime")
        # Runtime returns formatted string, no device_class or unit
        assert desc.device_class is None
        assert desc.native_unit_of_measurement is None


# =============================================================================
# Value Function Tests
# =============================================================================


class TestSystemSensorValueFunctions:
    """Test system sensor value functions."""

    def test_cpu_usage_value_fn(self) -> None:
        """Test CPU usage value function."""
        data = make_system_data(cpu_percent=45.5)
        desc = next(s for s in SYSTEM_SENSORS if s.key == "cpu_usage")
        assert desc.value_fn(data) == 45.5

    def test_cpu_usage_value_fn_none(self) -> None:
        """Test CPU usage value function with None."""
        data = make_system_data(cpu_percent=None)
        desc = next(s for s in SYSTEM_SENSORS if s.key == "cpu_usage")
        assert desc.value_fn(data) is None

    def test_ram_usage_value_fn(self) -> None:
        """Test RAM usage value function."""
        data = make_system_data(memory_percent=65.3)
        desc = next(s for s in SYSTEM_SENSORS if s.key == "ram_usage")
        assert desc.value_fn(data) == 65.3

    def test_ram_used_value_fn(self) -> None:
        """Test RAM used value function."""
        data = make_system_data(memory_used=8589934592)  # 8 GB
        desc = next(s for s in SYSTEM_SENSORS if s.key == "ram_used")
        assert desc.value_fn(data) == 8589934592

    def test_notifications_value_fn(self) -> None:
        """Test notifications value function."""
        data = make_system_data(notifications_unread=5)
        desc = next(s for s in SYSTEM_SENSORS if s.key == "notifications")
        assert desc.value_fn(data) == 5


class TestStorageSensorValueFunctions:
    """Test storage sensor value functions."""

    def test_array_state_value_fn(self) -> None:
        """Test array state value function."""
        data = make_storage_data(array_state="STARTED")
        desc = next(s for s in STORAGE_SENSORS if s.key == "array_state")
        assert desc.value_fn(data) == "started"

    def test_array_state_value_fn_none(self) -> None:
        """Test array state value function with None."""
        data = make_storage_data(array_state=None)
        desc = next(s for s in STORAGE_SENSORS if s.key == "array_state")
        assert desc.value_fn(data) is None

    def test_array_usage_value_fn(self) -> None:
        """Test array usage value function."""
        data = make_storage_data(
            array_state="STARTED",
            capacity_total=1000,
            capacity_used=500,
            capacity_free=500,
        )
        desc = next(s for s in STORAGE_SENSORS if s.key == "array_usage")
        assert desc.value_fn(data) == 50.0

    def test_array_used_value_fn(self) -> None:
        """Test array used value function (returns kilobytes)."""
        data = make_storage_data(
            array_state="STARTED",
            capacity_total=1000000,
            capacity_used=500000,
            capacity_free=500000,
        )
        desc = next(s for s in STORAGE_SENSORS if s.key == "array_used")
        assert desc.value_fn(data) == 500000


class TestDiskSensorValueFunctions:
    """Test disk sensor value functions."""

    def test_disk_usage_value_fn(self) -> None:
        """Test disk usage value function."""
        disk = ArrayDisk(id="disk1", fsSize=1000, fsUsed=500)
        desc = next(s for s in DISK_SENSORS if s.key == "usage")
        assert desc.value_fn(disk) == 50.0

    def test_disk_usage_value_fn_no_size(self) -> None:
        """Test disk usage value function with no size."""
        disk = ArrayDisk(id="disk1", fsSize=0, fsUsed=0)
        desc = next(s for s in DISK_SENSORS if s.key == "usage")
        assert desc.value_fn(disk) is None

    def test_disk_used_value_fn(self) -> None:
        """Test disk used value function."""
        disk = ArrayDisk(id="disk1", fsUsed=500000)
        desc = next(s for s in DISK_SENSORS if s.key == "used")
        assert desc.value_fn(disk) == 500000

    def test_disk_temp_value_fn(self) -> None:
        """Test disk temperature value function."""
        disk = ArrayDisk(id="disk1", temp=35)
        desc = next(s for s in DISK_SENSORS if s.key == "temp")
        assert desc.value_fn(disk) == 35


class TestShareSensorValueFunctions:
    """Test share sensor value functions."""

    def test_share_usage_value_fn(self) -> None:
        """Test share usage value function."""
        # 250 used, 750 free = 1000 total, 25% usage
        share = Share(id="share1", name="Test", used=250, free=750)
        desc = next(s for s in SHARE_SENSORS if s.key == "usage")
        assert desc.value_fn(share) == 25.0

    def test_share_usage_value_fn_no_data(self) -> None:
        """Test share usage value function with no data."""
        share = Share(id="share1", name="Test", used=0, free=0)
        desc = next(s for s in SHARE_SENSORS if s.key == "usage")
        assert desc.value_fn(share) is None

    def test_share_used_value_fn(self) -> None:
        """Test share used value function."""
        share = Share(id="share1", name="Test", used=250000)
        desc = next(s for s in SHARE_SENSORS if s.key == "used")
        assert desc.value_fn(share) == 250000


class TestUPSSensorValueFunctions:
    """Test UPS sensor value functions."""

    def test_ups_battery_value_fn(self) -> None:
        """Test UPS battery value function."""
        ups = UPSDevice(id="ups1", name="UPS", battery=UPSBattery(chargeLevel=85))
        desc = next(s for s in UPS_SENSORS if s.key == "battery")
        assert desc.value_fn(ups) == 85

    def test_ups_load_value_fn(self) -> None:
        """Test UPS load value function."""
        ups = UPSDevice(id="ups1", name="UPS", power=UPSPower(loadPercentage=45.5))
        desc = next(s for s in UPS_SENSORS if s.key == "load")
        assert desc.value_fn(ups) == 45.5

    def test_ups_runtime_value_fn(self) -> None:
        """Test UPS runtime value function (returns formatted string)."""
        ups = UPSDevice(
            id="ups1", name="UPS", battery=UPSBattery(estimatedRuntime=3661)
        )
        desc = next(s for s in UPS_SENSORS if s.key == "runtime")
        # 3661 seconds = 1 hour, 1 minute, 1 second
        assert desc.value_fn(ups) == "1 hour, 1 minute, 1 second"


# =============================================================================
# Entity Tests
# =============================================================================


class TestUnraidSystemSensorEntity:
    """Test UnraidSystemSensorEntity class."""

    def test_entity_creation(self) -> None:
        """Test basic entity creation."""
        coordinator = MagicMock()
        coordinator.data = make_system_data(cpu_percent=50.0)
        coordinator.last_update_success = True

        desc = next(s for s in SYSTEM_SENSORS if s.key == "cpu_usage")
        device_info = DeviceInfo(
            identifiers={(DOMAIN, "test-uuid")}, name="Test Server"
        )

        entity = UnraidSystemSensorEntity(
            coordinator=coordinator,
            description=desc,
            server_uuid="test-uuid",
            device_info=device_info,
        )

        assert entity.unique_id == "test-uuid_cpu_usage"
        assert entity.native_value == 50.0
        assert entity.available is True

    def test_entity_unavailable_when_coordinator_fails(self) -> None:
        """Test entity availability when coordinator update fails."""
        coordinator = MagicMock()
        coordinator.data = make_system_data()
        coordinator.last_update_success = False

        desc = next(s for s in SYSTEM_SENSORS if s.key == "cpu_usage")
        device_info = DeviceInfo(
            identifiers={(DOMAIN, "test-uuid")}, name="Test Server"
        )

        entity = UnraidSystemSensorEntity(
            coordinator=coordinator,
            description=desc,
            server_uuid="test-uuid",
            device_info=device_info,
        )

        assert entity.available is False


class TestUnraidDiskSensorEntity:
    """Test UnraidDiskSensorEntity class."""

    def test_disk_entity_creation(self) -> None:
        """Test disk sensor entity creation."""
        disk = ArrayDisk(id="disk1", name="Disk 1", fsSize=1000, fsUsed=500)
        coordinator = MagicMock()
        coordinator.data = make_storage_data(disks=[disk])
        coordinator.last_update_success = True

        desc = next(s for s in DISK_SENSORS if s.key == "usage")
        device_info = DeviceInfo(
            identifiers={(DOMAIN, "test-uuid")}, name="Test Server"
        )

        entity = UnraidDiskSensorEntity(
            coordinator=coordinator,
            description=desc,
            disk=disk,
            server_uuid="test-uuid",
            device_info=device_info,
        )

        assert entity.unique_id == "test-uuid_disk_disk1_usage"
        assert entity.native_value == 50.0
        assert entity._attr_translation_placeholders == {"disk_name": "Disk 1"}


class TestUnraidShareSensorEntity:
    """Test UnraidShareSensorEntity class."""

    def test_share_entity_creation(self) -> None:
        """Test share sensor entity creation.

        250 used + 750 free = 1000 total = 25% usage.
        """
        share = Share(id="share1", name="Media", used=250, free=750)
        coordinator = MagicMock()
        coordinator.data = make_storage_data(shares=[share])
        coordinator.last_update_success = True

        desc = next(s for s in SHARE_SENSORS if s.key == "usage")
        device_info = DeviceInfo(
            identifiers={(DOMAIN, "test-uuid")}, name="Test Server"
        )

        entity = UnraidShareSensorEntity(
            coordinator=coordinator,
            description=desc,
            share=share,
            server_uuid="test-uuid",
            device_info=device_info,
        )

        assert entity.unique_id == "test-uuid_share_share1_usage"
        assert entity.native_value == 25.0
        assert entity._attr_translation_placeholders == {"share_name": "Media"}


class TestUnraidUPSSensorEntity:
    """Test UnraidUPSSensorEntity class."""

    def test_ups_entity_creation(self) -> None:
        """Test UPS sensor entity creation."""
        ups = UPSDevice(id="ups1", name="APC", battery=UPSBattery(chargeLevel=85))
        coordinator = MagicMock()
        coordinator.data = make_system_data(ups_devices=[ups])
        coordinator.last_update_success = True

        desc = next(s for s in UPS_SENSORS if s.key == "battery")
        device_info = DeviceInfo(
            identifiers={(DOMAIN, "test-uuid")}, name="Test Server"
        )

        entity = UnraidUPSSensorEntity(
            coordinator=coordinator,
            description=desc,
            ups=ups,
            server_uuid="test-uuid",
            device_info=device_info,
        )

        assert entity.unique_id == "test-uuid_ups_ups1_battery"
        assert entity.native_value == 85
        assert entity._attr_translation_placeholders == {"ups_name": "APC"}


class TestUnraidUPSPowerSensorEntity:
    """Test UnraidUPSPowerSensorEntity class."""

    def test_ups_power_entity_creation(self) -> None:
        """Test UPS power sensor entity creation.

        Power = load_percentage * nominal_power / 100
        12% load * 800W nominal = 96W
        """
        ups = UPSDevice(id="ups1", name="APC", power=UPSPower(loadPercentage=12.0))
        coordinator = MagicMock()
        coordinator.data = make_system_data(ups_devices=[ups])
        coordinator.last_update_success = True

        device_info = DeviceInfo(
            identifiers={(DOMAIN, "test-uuid")}, name="Test Server"
        )

        entity = UnraidUPSPowerSensorEntity(
            coordinator=coordinator,
            ups=ups,
            server_uuid="test-uuid",
            device_info=device_info,
            nominal_power=800,
        )

        assert entity.unique_id == "test-uuid_ups_ups1_power"
        assert entity.native_value == 96.0
        assert entity._attr_translation_placeholders == {"ups_name": "APC"}
        assert entity.device_class == SensorDeviceClass.POWER

    def test_ups_power_entity_no_load(self) -> None:
        """Test UPS power sensor returns None when load is unavailable."""
        ups = UPSDevice(id="ups1", name="APC", power=UPSPower())
        coordinator = MagicMock()
        coordinator.data = make_system_data(ups_devices=[ups])
        coordinator.last_update_success = True

        device_info = DeviceInfo(
            identifiers={(DOMAIN, "test-uuid")}, name="Test Server"
        )

        entity = UnraidUPSPowerSensorEntity(
            coordinator=coordinator,
            ups=ups,
            server_uuid="test-uuid",
            device_info=device_info,
            nominal_power=800,
        )

        assert entity.native_value is None
