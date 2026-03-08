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
