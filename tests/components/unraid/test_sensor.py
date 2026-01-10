"""Tests for Unraid sensor entities using entity descriptions."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

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
    UnraidUPSSensorEntity,
    _get_nested,
    _parse_uptime,
)
from homeassistant.const import UnitOfInformation, UnitOfTemperature, UnitOfTime
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory

from .conftest import make_storage_data, make_system_data

# =============================================================================
# Helper Function Tests
# =============================================================================


class TestGetNested:
    """Test _get_nested helper function."""

    def test_get_nested_simple(self) -> None:
        """Test _get_nested with simple path."""
        data = {"a": {"b": {"c": 42}}}
        assert _get_nested(data, "a", "b", "c") == 42

    def test_get_nested_missing(self) -> None:
        """Test _get_nested with missing key."""
        data = {"a": {"b": {}}}
        assert _get_nested(data, "a", "b", "c") is None

    def test_get_nested_with_default(self) -> None:
        """Test _get_nested with default value."""
        data = {"a": {}}
        assert _get_nested(data, "a", "b", "c", default="default") == "default"

    def test_get_nested_not_dict(self) -> None:
        """Test _get_nested when value is not a dict."""
        data = {"a": 123}
        assert _get_nested(data, "a", "b") is None


class TestParseUptime:
    """Test _parse_uptime helper function."""

    def test_parse_uptime_none(self) -> None:
        """Test _parse_uptime with None input."""
        assert _parse_uptime(None) is None

    def test_parse_uptime_iso_format(self) -> None:
        """Test _parse_uptime with ISO format string."""
        result = _parse_uptime("2024-01-15T10:30:00+00:00")
        assert result == datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)

    def test_parse_uptime_z_suffix(self) -> None:
        """Test _parse_uptime with Z suffix."""
        result = _parse_uptime("2024-01-15T10:30:00Z")
        assert result == datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)

    def test_parse_uptime_invalid(self) -> None:
        """Test _parse_uptime with invalid string."""
        assert _parse_uptime("not-a-date") is None


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
        assert desc.entity_category == EntityCategory.DIAGNOSTIC

    def test_cpu_temp_sensor_description(self) -> None:
        """Test CPU temperature sensor description."""
        desc = next(s for s in SYSTEM_SENSORS if s.key == "cpu_temp")
        assert desc.device_class == SensorDeviceClass.TEMPERATURE
        assert desc.native_unit_of_measurement == UnitOfTemperature.CELSIUS

    def test_uptime_sensor_description(self) -> None:
        """Test uptime sensor description."""
        desc = next(s for s in SYSTEM_SENSORS if s.key == "uptime")
        assert desc.device_class == SensorDeviceClass.TIMESTAMP
        assert desc.entity_category == EntityCategory.DIAGNOSTIC

    def test_notifications_sensor_description(self) -> None:
        """Test notifications sensor description."""
        desc = next(s for s in SYSTEM_SENSORS if s.key == "notifications")
        assert desc.state_class == SensorStateClass.MEASUREMENT
        assert desc.entity_category == EntityCategory.DIAGNOSTIC


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
        assert desc.entity_category == EntityCategory.DIAGNOSTIC


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
        assert desc.device_class == SensorDeviceClass.DURATION
        assert desc.native_unit_of_measurement == UnitOfTime.SECONDS


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

    def test_cpu_temp_value_fn(self) -> None:
        """Test CPU temperature value function (average of packages)."""
        data = make_system_data(cpu_temps=[45.0, 47.0, 49.0])
        desc = next(s for s in SYSTEM_SENSORS if s.key == "cpu_temp")
        result = desc.value_fn(data)
        assert result is not None
        assert isinstance(result, (int, float))
        assert abs(float(result) - 47.0) < 0.01  # Average of 45, 47, 49

    def test_cpu_temp_value_fn_empty(self) -> None:
        """Test CPU temperature value function with empty temps."""
        data = make_system_data(cpu_temps=[])
        desc = next(s for s in SYSTEM_SENSORS if s.key == "cpu_temp")
        assert desc.value_fn(data) is None

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
            capacity={"kilobytes": {"total": 1000, "used": 500, "free": 500}},
        )
        desc = next(s for s in STORAGE_SENSORS if s.key == "array_usage")
        assert desc.value_fn(data) == 50.0

    def test_array_used_value_fn(self) -> None:
        """Test array used value function (returns kilobytes)."""
        data = make_storage_data(
            array_state="STARTED",
            capacity={"kilobytes": {"total": 1000000, "used": 500000, "free": 500000}},
        )
        desc = next(s for s in STORAGE_SENSORS if s.key == "array_used")
        assert desc.value_fn(data) == 500000


class TestDiskSensorValueFunctions:
    """Test disk sensor value functions."""

    def test_disk_usage_value_fn(self) -> None:
        """Test disk usage value function."""
        disk = {"id": "disk1", "fsSize": 1000, "fsUsed": 500}
        desc = next(s for s in DISK_SENSORS if s.key == "usage")
        assert desc.value_fn(disk) == 50.0

    def test_disk_usage_value_fn_no_size(self) -> None:
        """Test disk usage value function with no size."""
        disk = {"id": "disk1", "fsSize": 0, "fsUsed": 0}
        desc = next(s for s in DISK_SENSORS if s.key == "usage")
        assert desc.value_fn(disk) is None

    def test_disk_used_value_fn(self) -> None:
        """Test disk used value function."""
        disk = {"id": "disk1", "fsUsed": 500000}
        desc = next(s for s in DISK_SENSORS if s.key == "used")
        assert desc.value_fn(disk) == 500000

    def test_disk_temp_value_fn(self) -> None:
        """Test disk temperature value function."""
        disk = {"id": "disk1", "temp": 35}
        desc = next(s for s in DISK_SENSORS if s.key == "temp")
        assert desc.value_fn(disk) == 35


class TestShareSensorValueFunctions:
    """Test share sensor value functions."""

    def test_share_usage_value_fn(self) -> None:
        """Test share usage value function."""
        share = {"id": "share1", "size": 1000, "used": 250}
        desc = next(s for s in SHARE_SENSORS if s.key == "usage")
        assert desc.value_fn(share) == 25.0

    def test_share_used_value_fn(self) -> None:
        """Test share used value function."""
        share = {"id": "share1", "used": 250000}
        desc = next(s for s in SHARE_SENSORS if s.key == "used")
        assert desc.value_fn(share) == 250000


class TestUPSSensorValueFunctions:
    """Test UPS sensor value functions."""

    def test_ups_battery_value_fn(self) -> None:
        """Test UPS battery value function."""
        ups = {"id": "ups1", "battery": {"chargeLevel": 85}}
        desc = next(s for s in UPS_SENSORS if s.key == "battery")
        assert desc.value_fn(ups) == 85

    def test_ups_load_value_fn(self) -> None:
        """Test UPS load value function."""
        ups = {"id": "ups1", "power": {"loadPercentage": 45.5}}
        desc = next(s for s in UPS_SENSORS if s.key == "load")
        assert desc.value_fn(ups) == 45.5

    def test_ups_runtime_value_fn(self) -> None:
        """Test UPS runtime value function (returns seconds)."""
        ups = {"id": "ups1", "battery": {"estimatedRuntime": 3600}}
        desc = next(s for s in UPS_SENSORS if s.key == "runtime")
        assert desc.value_fn(ups) == 3600


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
        disk = {"id": "disk1", "name": "Disk 1", "fsSize": 1000, "fsUsed": 500}
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
        """Test share sensor entity creation."""
        share = {"id": "share1", "name": "Media", "size": 1000, "used": 250}
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
        ups = {"id": "ups1", "name": "APC", "battery": {"chargeLevel": 85}}
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
