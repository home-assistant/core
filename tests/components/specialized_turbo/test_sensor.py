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


def test_battery_capacity_wh() -> None:
    """Test battery capacity value function."""
    snap = TelemetrySnapshot()
    snap.battery.capacity_wh = 604.0
    desc = _get_desc("battery_capacity_wh")
    assert desc.value_fn(snap) == 604.0


def test_battery_remaining_wh() -> None:
    """Test battery remaining value function."""
    snap = TelemetrySnapshot()
    snap.battery.remaining_wh = 302.0
    desc = _get_desc("battery_remaining_wh")
    assert desc.value_fn(snap) == 302.0


def test_battery_health() -> None:
    """Test battery health value function."""
    snap = TelemetrySnapshot()
    snap.battery.health_pct = 95
    desc = _get_desc("battery_health")
    assert desc.value_fn(snap) == 95


def test_battery_temp() -> None:
    """Test battery temperature value function."""
    snap = TelemetrySnapshot()
    snap.battery.temp_c = 25
    desc = _get_desc("battery_temp")
    assert desc.value_fn(snap) == 25


def test_battery_charge_cycles() -> None:
    """Test battery charge cycles value function."""
    snap = TelemetrySnapshot()
    snap.battery.charge_cycles = 150
    desc = _get_desc("battery_charge_cycles")
    assert desc.value_fn(snap) == 150


def test_battery_voltage() -> None:
    """Test battery voltage value function."""
    snap = TelemetrySnapshot()
    snap.battery.voltage_v = 36.5
    desc = _get_desc("battery_voltage")
    assert desc.value_fn(snap) == 36.5


def test_battery_current() -> None:
    """Test battery current value function."""
    snap = TelemetrySnapshot()
    snap.battery.current_a = 5.0
    desc = _get_desc("battery_current")
    assert desc.value_fn(snap) == 5.0


def test_speed() -> None:
    """Test speed value function."""
    snap = TelemetrySnapshot()
    snap.motor.speed_kmh = 25.5
    desc = _get_desc("speed")
    assert desc.value_fn(snap) == 25.5


def test_rider_power() -> None:
    """Test rider power value function."""
    snap = TelemetrySnapshot()
    snap.motor.rider_power_w = 150.0
    desc = _get_desc("rider_power")
    assert desc.value_fn(snap) == 150.0


def test_motor_power() -> None:
    """Test motor power value function."""
    snap = TelemetrySnapshot()
    snap.motor.motor_power_w = 250.0
    desc = _get_desc("motor_power")
    assert desc.value_fn(snap) == 250.0


def test_cadence() -> None:
    """Test cadence value function."""
    snap = TelemetrySnapshot()
    snap.motor.cadence_rpm = 80.0
    desc = _get_desc("cadence")
    assert desc.value_fn(snap) == 80.0


def test_odometer() -> None:
    """Test odometer value function."""
    snap = TelemetrySnapshot()
    snap.motor.odometer_km = 1234.5
    desc = _get_desc("odometer")
    assert desc.value_fn(snap) == 1234.5


def test_motor_temp() -> None:
    """Test motor temperature value function."""
    snap = TelemetrySnapshot()
    snap.motor.motor_temp_c = 45
    desc = _get_desc("motor_temp")
    assert desc.value_fn(snap) == 45


def test_assist_eco_pct() -> None:
    """Test ECO assist percentage value function."""
    snap = TelemetrySnapshot()
    snap.settings.assist_lev1_pct = 30
    desc = _get_desc("assist_eco_pct")
    assert desc.value_fn(snap) == 30


def test_assist_trail_pct() -> None:
    """Test trail assist percentage value function."""
    snap = TelemetrySnapshot()
    snap.settings.assist_lev2_pct = 60
    desc = _get_desc("assist_trail_pct")
    assert desc.value_fn(snap) == 60


def test_assist_turbo_pct() -> None:
    """Test turbo assist percentage value function."""
    snap = TelemetrySnapshot()
    snap.settings.assist_lev3_pct = 100
    desc = _get_desc("assist_turbo_pct")
    assert desc.value_fn(snap) == 100


# --- Assist level name function ---


def test_assist_level_name_none() -> None:
    """Test assist level name when None."""
    snap = TelemetrySnapshot()
    assert _assist_level_name(snap) is None


def test_assist_level_name_off() -> None:
    """Test assist level name for OFF."""
    snap = TelemetrySnapshot()
    snap.motor.assist_level = AssistLevel.OFF
    assert _assist_level_name(snap) == "Off"


def test_assist_level_name_eco() -> None:
    """Test assist level name for ECO."""
    snap = TelemetrySnapshot()
    snap.motor.assist_level = AssistLevel.ECO
    assert _assist_level_name(snap) == "Eco"


def test_assist_level_name_trail() -> None:
    """Test assist level name for TRAIL."""
    snap = TelemetrySnapshot()
    snap.motor.assist_level = AssistLevel.TRAIL
    assert _assist_level_name(snap) == "Trail"


def test_assist_level_name_turbo() -> None:
    """Test assist level name for TURBO."""
    snap = TelemetrySnapshot()
    snap.motor.assist_level = AssistLevel.TURBO
    assert _assist_level_name(snap) == "Turbo"


def test_assist_level_name_unknown_int() -> None:
    """Test assist level name with unknown int value."""
    snap = TelemetrySnapshot()
    snap.motor.assist_level = 99
    assert _assist_level_name(snap) == "99"


# --- Sensor description metadata ---


def test_sensor_descriptions_count() -> None:
    """Test that all 18 sensor descriptions are defined."""
    assert len(SENSOR_DESCRIPTIONS) == 18


def test_parallel_updates_zero() -> None:
    """Test PARALLEL_UPDATES is 0 for push-based coordinator."""
    assert PARALLEL_UPDATES == 0


def test_all_descriptions_have_translation_key() -> None:
    """Test that all descriptions have a translation key."""
    for desc in SENSOR_DESCRIPTIONS:
        assert desc.translation_key is not None, f"{desc.key} missing translation_key"


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
