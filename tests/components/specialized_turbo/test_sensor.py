"""Tests for Specialized Turbo sensor entities."""

from __future__ import annotations

from specialized_turbo import AssistLevel, TelemetrySnapshot

from homeassistant.components.specialized_turbo.sensor import (
    PARALLEL_UPDATES,
    SENSOR_DESCRIPTIONS,
    SpecializedSensorEntityDescription,
    _assist_level_name,
)

# --- Value function tests ---


def test_battery_charge_pct() -> None:
    """Test battery charge percent value function."""
    snap = TelemetrySnapshot()
    snap.battery.charge_pct = 85
    desc = _get_desc("battery_charge_percent")
    assert desc.value_fn(snap) == 85


def test_speed() -> None:
    """Test speed value function."""
    snap = TelemetrySnapshot()
    snap.motor.speed_kmh = 25.5
    desc = _get_desc("speed")
    assert desc.value_fn(snap) == 25.5


# --- Assist level name function ---


def test_assist_level_name_none() -> None:
    """Test assist level name when None."""
    snap = TelemetrySnapshot()
    assert _assist_level_name(snap) is None


def test_assist_level_name_off() -> None:
    """Test assist level name for OFF."""
    snap = TelemetrySnapshot()
    snap.motor.assist_level = AssistLevel.OFF
    assert _assist_level_name(snap) == "off"


def test_assist_level_name_eco() -> None:
    """Test assist level name for ECO."""
    snap = TelemetrySnapshot()
    snap.motor.assist_level = AssistLevel.ECO
    assert _assist_level_name(snap) == "eco"


def test_assist_level_name_trail() -> None:
    """Test assist level name for TRAIL."""
    snap = TelemetrySnapshot()
    snap.motor.assist_level = AssistLevel.TRAIL
    assert _assist_level_name(snap) == "trail"


def test_assist_level_name_turbo() -> None:
    """Test assist level name for TURBO."""
    snap = TelemetrySnapshot()
    snap.motor.assist_level = AssistLevel.TURBO
    assert _assist_level_name(snap) == "turbo"


def test_assist_level_name_unknown_int() -> None:
    """Test assist level name with unknown int value."""
    snap = TelemetrySnapshot()
    snap.motor.assist_level = 99
    assert _assist_level_name(snap) is None


# --- Sensor description metadata ---


def test_sensor_descriptions_count() -> None:
    """Test that all 26 sensor descriptions are defined."""
    assert len(SENSOR_DESCRIPTIONS) == 26


def test_parallel_updates_zero() -> None:
    """Test PARALLEL_UPDATES is 0 for push-based coordinator."""
    assert PARALLEL_UPDATES == 0


def test_all_descriptions_have_translation_key_or_device_class() -> None:
    """Test that all descriptions have a translation key or device class for naming."""
    for desc in SENSOR_DESCRIPTIONS:
        assert desc.translation_key is not None or desc.device_class is not None, (
            f"{desc.key} has neither translation_key nor device_class"
        )


def test_value_fn_returns_none_for_empty_snapshot() -> None:
    """Test that all value functions handle empty snapshot gracefully."""
    snap = TelemetrySnapshot()
    for desc in SENSOR_DESCRIPTIONS:
        value = desc.value_fn(snap)
        assert value is None, f"{desc.key} returned {value} for empty snapshot"


# --- Helper ---


def _get_desc(key: str) -> SpecializedSensorEntityDescription:
    """Get a sensor description by key."""
    for desc in SENSOR_DESCRIPTIONS:
        if desc.key == key:
            return desc
    raise KeyError(f"No sensor description with key {key}")
