"""Tests for Unraid sensor entities."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.components.unraid.sensor import (
    SYSTEM_SENSORS,
    _format_duration,
    _parse_uptime,
)
from homeassistant.const import UnitOfInformation

from .conftest import make_system_data


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
        boot_time = datetime.now(UTC) - timedelta(hours=1, minutes=30, seconds=45)
        result = _parse_uptime(boot_time)
        assert result is not None
        assert "hour" in result
        assert "minute" in result


class TestSystemSensorDescriptions:
    """Test system sensor entity descriptions."""

    def test_cpu_usage_sensor_description(self) -> None:
        """Test CPU usage sensor description."""
        desc = next(s for s in SYSTEM_SENSORS if s.key == "cpu_usage")
        assert desc.native_unit_of_measurement == "%"
        assert desc.state_class == SensorStateClass.MEASUREMENT
        assert desc.translation_key == "cpu_usage"

    def test_cpu_temp_sensor_description(self) -> None:
        """Test CPU temperature sensor description."""
        desc = next(s for s in SYSTEM_SENSORS if s.key == "cpu_temp")
        assert desc.device_class == SensorDeviceClass.TEMPERATURE
        assert desc.state_class == SensorStateClass.MEASUREMENT

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
        assert desc.device_class is None
        assert desc.native_unit_of_measurement is None


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

    def test_cpu_temp_value_fn(self) -> None:
        """Test CPU temperature value function."""
        data = make_system_data(cpu_temperature=55.0)
        desc = next(s for s in SYSTEM_SENSORS if s.key == "cpu_temp")
        assert desc.value_fn(data) == 55.0

    def test_ram_usage_value_fn(self) -> None:
        """Test RAM usage value function."""
        data = make_system_data(memory_percent=65.3)
        desc = next(s for s in SYSTEM_SENSORS if s.key == "ram_usage")
        assert desc.value_fn(data) == 65.3

    def test_ram_used_value_fn(self) -> None:
        """Test RAM used value function."""
        data = make_system_data(memory_used=8589934592)
        desc = next(s for s in SYSTEM_SENSORS if s.key == "ram_used")
        assert desc.value_fn(data) == 8589934592
