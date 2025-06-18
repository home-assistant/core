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
        fan_data = DreoFanDeviceData.process_fan_data("DR-HTF001S", status)
        assert fan_data.speed_percentage == expected_percentage


async def test_data_processing_with_missing_model_config() -> None:
    """Test data processing behavior when device model is not in configuration."""
    status = {"connected": True, "power_switch": True, "speed": 3}
    fan_data = DreoFanDeviceData.process_fan_data("UNKNOWN-MODEL", status)

    assert fan_data.available is True
    assert fan_data.is_on is True

    assert fan_data.speed_percentage is None


async def test_data_type_conversion_algorithms() -> None:
    """Test core data type conversion algorithms used across platforms."""
    status = {
        "connected": True,
        "power_switch": True,
        "mode": 123,
        "oscillate": 1,
        "speed": 3,
    }

    fan_data = DreoFanDeviceData.process_fan_data("DR-HTF001S", status)

    assert fan_data.mode == "123"
    assert fan_data.oscillate is True
    assert fan_data.speed_percentage == 50
