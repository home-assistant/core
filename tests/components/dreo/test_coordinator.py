"""Test dreo coordinator core logic.

Only tests for core logic that cannot be tested through platforms should be here.
Most coordinator functionality should be tested through platform tests (test_fan.py).
"""

from homeassistant.components.dreo.coordinator import DreoFanDeviceData


async def test_speed_range_conversion_logic() -> None:
    """Test speed range conversion algorithm - core logic that spans multiple platforms."""

    test_cases = [
        ({"speed": 1}, 16),
        ({"speed": 3}, 50),
        ({"speed": 6}, 100),
        ({"speed": 0}, 0),
    ]

    for status, expected_percentage in test_cases:
        status.update({"connected": True, "power_switch": True})
        model_config = {
            "preset_modes": ["Sleep", "Auto", "Natural", "Normal"],
            "speed_range": [1, 6],
        }
        fan_data = DreoFanDeviceData.process_fan_data(status, model_config)
        assert fan_data.speed_percentage == expected_percentage


async def test_data_type_conversion_algorithms() -> None:
    """Test core data type conversion algorithms used across platforms."""
    status = {
        "connected": True,
        "power_switch": True,
        "mode": 123,
        "oscillate": 1,
        "speed": 3,
    }
    model_config = {
        "preset_modes": ["Sleep", "Auto", "Natural", "Normal"],
        "speed_range": [1, 6],
    }

    fan_data = DreoFanDeviceData.process_fan_data(status, model_config)

    assert fan_data.mode == "123"
    assert fan_data.oscillate is True
    assert fan_data.speed_percentage == 50


async def test_data_processing_with_missing_speed_range() -> None:
    """Test data processing behavior when speed_range is not in model config."""
    status = {"connected": True, "power_switch": True, "speed": 3}
    model_config = {
        "preset_modes": ["Sleep", "Auto", "Natural", "Normal"],
    }
    fan_data = DreoFanDeviceData.process_fan_data(status, model_config)

    assert fan_data.available is True
    assert fan_data.is_on is True
    assert fan_data.speed_percentage is None


async def test_process_fan_data_edge_cases() -> None:
    """Test edge cases in fan data processing."""

    status = {"connected": False, "power_switch": False}
    model_config = {
        "preset_modes": ["Sleep", "Auto", "Natural", "Normal"],
        "speed_range": [1, 6],
    }

    fan_data = DreoFanDeviceData.process_fan_data(status, model_config)
    assert fan_data.available is False
    assert fan_data.is_on is False
    assert fan_data.mode is None
    assert fan_data.oscillate is None
    assert fan_data.speed_percentage is None

    status_zero_oscillate = {
        "connected": True,
        "power_switch": True,
        "oscillate": 0,
        "speed": 3,
    }

    fan_data_zero = DreoFanDeviceData.process_fan_data(
        status_zero_oscillate, model_config
    )
    assert fan_data_zero.oscillate is False
    assert fan_data_zero.speed_percentage == 50
