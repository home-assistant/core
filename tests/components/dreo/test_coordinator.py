"""Test dreo coordinator core logic.

Only tests for core logic that cannot be tested through platforms should be here.
Most coordinator functionality should be tested through platform tests (test_fan.py).
"""

from homeassistant.components.dreo.const import (
    FIELD_CONNECTED,
    FIELD_MODE,
    FIELD_OSCILLATE,
    FIELD_POWER_ON,
    FIELD_SPEED,
)
from homeassistant.components.dreo.coordinator import DreoFanDeviceData


async def test_speed_range_conversion_logic() -> None:
    """Test speed range conversion algorithm - core logic that spans multiple platforms."""

    test_cases = [
        ({FIELD_SPEED: 1}, 16),
        ({FIELD_SPEED: 3}, 50),
        ({FIELD_SPEED: 6}, 100),
        ({FIELD_SPEED: 0}, 0),
    ]

    for status, expected_percentage in test_cases:
        status.update({FIELD_CONNECTED: True, FIELD_POWER_ON: True})
        model_config = {
            "preset_modes": ["Sleep", "Auto", "Natural", "Normal"],
            "speed_range": [1, 6],
        }
        fan_data = DreoFanDeviceData.process_fan_data(status, model_config)
        assert fan_data.speed_percentage == expected_percentage


async def test_data_type_conversion_algorithms() -> None:
    """Test core data type conversion algorithms used across platforms."""
    status = {
        FIELD_CONNECTED: True,
        FIELD_POWER_ON: True,
        FIELD_MODE: 123,
        FIELD_OSCILLATE: 1,
        FIELD_SPEED: 3,
    }
    model_config = {
        "preset_modes": ["Sleep", "Auto", "Natural", "Normal"],
        "speed_range": [1, 6],
    }

    fan_data = DreoFanDeviceData.process_fan_data(status, model_config)

    assert fan_data.mode == "123"
    assert fan_data.oscillate is True
    assert fan_data.speed_percentage == 50


async def test_speed_values_list_conversion_logic() -> None:
    """Test speed conversion from explicit supported speed values."""
    status = {FIELD_CONNECTED: True, FIELD_POWER_ON: True, FIELD_SPEED: 7}
    model_config = {
        "preset_modes": ["Sleep", "Auto", "Natural", "Normal"],
        "speed_range": [1, 3, 5, 7, 9, 12],
    }

    fan_data = DreoFanDeviceData.process_fan_data(status, model_config)

    assert fan_data.speed_percentage == 66


async def test_data_processing_with_missing_speed_range() -> None:
    """Test data processing behavior when speed_range is not in model config."""
    status = {FIELD_CONNECTED: True, FIELD_POWER_ON: True, FIELD_SPEED: 3}
    model_config = {
        "preset_modes": ["Sleep", "Auto", "Natural", "Normal"],
    }
    fan_data = DreoFanDeviceData.process_fan_data(status, model_config)

    assert fan_data.is_on is True
    assert fan_data.speed_percentage is None


async def test_process_fan_data_edge_cases() -> None:
    """Test edge cases in fan data processing."""

    status = {FIELD_POWER_ON: False}
    model_config = {
        "preset_modes": ["Sleep", "Auto", "Natural", "Normal"],
        "speed_range": [1, 6],
    }

    fan_data = DreoFanDeviceData.process_fan_data(status, model_config)
    assert fan_data.is_on is False
    assert fan_data.mode is None
    assert fan_data.oscillate is None
    assert fan_data.speed_percentage is None

    status_zero_oscillate = {
        FIELD_CONNECTED: True,
        FIELD_POWER_ON: True,
        FIELD_OSCILLATE: 0,
        FIELD_SPEED: 3,
    }

    fan_data_zero = DreoFanDeviceData.process_fan_data(
        status_zero_oscillate, model_config
    )
    assert fan_data_zero.oscillate is False
    assert fan_data_zero.speed_percentage == 50


async def test_process_fan_data_zero_speed() -> None:
    """Test zero speed is reported correctly."""
    status = {FIELD_CONNECTED: True, FIELD_POWER_ON: True, FIELD_SPEED: 0}
    model_config = {
        "preset_modes": ["Sleep", "Auto", "Natural", "Normal"],
        "speed_range": [1, 6],
    }

    fan_data = DreoFanDeviceData.process_fan_data(status, model_config)

    assert fan_data.speed_percentage == 0
