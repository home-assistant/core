"""Tests for Kaiterra sensor entities."""

from __future__ import annotations

from types import SimpleNamespace

from homeassistant.components.kaiterra.sensor import SENSORS, KaiterraSensor
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass


def _build_sensor(data: dict[str, dict[str, object]], key: str) -> KaiterraSensor:
    """Build a Kaiterra sensor entity for a specific sensor key."""
    coordinator = SimpleNamespace(
        data=data,
        device_id="device-123",
        device_name="Office",
        last_update_success=True,
    )
    description = next(description for description in SENSORS if description.key == key)
    return KaiterraSensor(coordinator, description)


def test_aqi_sensor_uses_aqi_sensor_semantics() -> None:
    """Test the AQI sensor exposes AQI measurement metadata."""
    sensor = _build_sensor({"aqi": {"value": 78}}, "aqi")

    assert sensor.device_class is SensorDeviceClass.AQI
    assert sensor.state_class is SensorStateClass.MEASUREMENT
    assert sensor.native_value == 78


def test_native_value_filters_invalid_api_value_types() -> None:
    """Test invalid API values are not exposed as entity state."""
    sensor = _build_sensor({"aqi": {"value": {"raw": 78}}}, "aqi")

    assert sensor.native_value is None


def test_temperature_sensor_normalizes_fahrenheit_units() -> None:
    """Test temperature sensors normalize Fahrenheit units."""
    sensor = _build_sensor({"rtemp": {"value": 72.3, "unit": "F"}}, "rtemp")

    assert sensor.native_unit_of_measurement == "°F"


def test_temperature_sensor_normalizes_celsius_units() -> None:
    """Test temperature sensors normalize Celsius units."""
    sensor = _build_sensor({"rtemp": {"value": 22.3, "unit": "C"}}, "rtemp")

    assert sensor.native_unit_of_measurement == "°C"


def test_sensor_returns_empty_data_for_invalid_payload_shape() -> None:
    """Test non-dict payloads are treated as missing sensor data."""
    sensor = _build_sensor({"tvoc": "invalid"}, "tvoc")

    assert sensor.native_value is None
