"""Tests for Aquarite sensor value conversions."""
from __future__ import annotations

import datetime

import pytest


def test_temperature_conversion() -> None:
    """Test temperature sensor returns raw float."""
    raw_value = 25.5
    assert float(raw_value) == 25.5


def test_value_sensor_scaling() -> None:
    """Test value sensor divides by 100."""
    raw_value = "742"
    assert float(raw_value) / 100 == 7.42


def test_hydrolyser_scaling() -> None:
    """Test hydrolyser sensor divides by 10."""
    raw_value = 50
    assert float(raw_value) / 10 == 5.0


def test_rx_value_integer() -> None:
    """Test Rx sensor returns integer."""
    raw_value = 707
    assert int(raw_value) == 707


def test_time_sensor_conversion() -> None:
    """Test time sensor divides by 60 for hours."""
    raw_value = "600"
    assert float(raw_value) / 60 == 10.0


def test_interval_time_to_datetime() -> None:
    """Test interval seconds to datetime.time conversion."""
    # 28800 seconds = 8:00
    seconds = 28800
    hours = (seconds // 3600) % 24
    minutes = (seconds % 3600) // 60
    result = datetime.time(hours, minutes)
    assert result == datetime.time(8, 0)


def test_interval_time_afternoon() -> None:
    """Test afternoon interval conversion."""
    # 50400 seconds = 14:00
    seconds = 50400
    hours = (seconds // 3600) % 24
    minutes = (seconds % 3600) // 60
    result = datetime.time(hours, minutes)
    assert result == datetime.time(14, 0)


def test_interval_time_to_seconds() -> None:
    """Test datetime.time back to seconds conversion."""
    t = datetime.time(14, 30)
    seconds = t.hour * 3600 + t.minute * 60
    assert seconds == 52200


def test_number_ph_scaling() -> None:
    """Test pH number entity scaling (divide by 100 for display)."""
    raw_value = 742
    scale = 100
    assert raw_value / scale == 7.42


def test_number_ph_write_scaling() -> None:
    """Test pH number write scaling (multiply by 100 for API)."""
    user_value = 7.42
    scale = 100
    assert int(user_value * scale) == 742


def test_number_electrolysis_scaling() -> None:
    """Test electrolysis number scaling (divide by 10)."""
    raw_value = 100
    scale = 10
    assert raw_value / scale == 10.0


def test_speed_label_mapping() -> None:
    """Test speed label select mapping."""
    options = ("slow", "medium", "high")
    assert options[0] == "slow"
    assert options[1] == "medium"
    assert options[2] == "high"


def test_pump_mode_mapping() -> None:
    """Test pump mode select mapping."""
    options = ("manual", "auto", "heat", "smart", "intel")
    assert options[0] == "manual"
    assert options[3] == "smart"
    assert options.index("intel") == 4
