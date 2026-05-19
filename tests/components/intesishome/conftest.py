"""Fixtures for IntesisHome tests."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

MOCK_DEVICE_ID = "12345"
MOCK_DEVICE_NAME = "MOCK DEVICE"

# State values matching pyintesishome test constants (decoded to HA values)
MOCK_VAL_MODE = "cool"
MOCK_VAL_FAN_SPEED = "quiet"
MOCK_VAL_VVANE = "manual2"
MOCK_VAL_HVANE = "manual3"
MOCK_VAL_SETPOINT = 21.0
MOCK_VAL_TEMP = 24.0
MOCK_VAL_MIN_SET = 18.0
MOCK_VAL_MAX_SET = 30.0
MOCK_VAL_OUT_TEMP = 26.0
MOCK_VAL_PRESET = "eco"

MOCK_DEVICE = {
    "name": MOCK_DEVICE_NAME,
    "climate_working_mode": True,
}

PLATFORM_CONFIG = {
    "climate": {
        "platform": "intesishome",
        "username": "user@example.com",
        "password": "password",
        "device": "IntesisHome",
    }
}


@pytest.fixture
def mock_controller():
    """Mock IntesisHome controller."""
    controller = MagicMock(name="IntesisController")

    controller.device_type = "IntesisHome"
    controller.is_connected = True

    # Capability queries
    controller.get_devices.return_value = {MOCK_DEVICE_ID: MOCK_DEVICE}
    controller.has_setpoint_control.return_value = True
    controller.has_vertical_swing.return_value = True
    controller.has_horizontal_swing.return_value = True
    controller.get_fan_speed_list.return_value = [
        "auto",
        "quiet",
        "low",
        "medium",
        "high",
    ]
    controller.get_mode_list.return_value = ["auto", "heat", "cool", "dry", "fan"]

    # State queries
    controller.is_on.return_value = True
    controller.get_temperature.return_value = MOCK_VAL_TEMP
    controller.get_setpoint.return_value = MOCK_VAL_SETPOINT
    controller.get_min_setpoint.return_value = MOCK_VAL_MIN_SET
    controller.get_max_setpoint.return_value = MOCK_VAL_MAX_SET
    controller.get_fan_speed.return_value = MOCK_VAL_FAN_SPEED
    controller.get_mode.return_value = MOCK_VAL_MODE
    controller.get_preset_mode.return_value = MOCK_VAL_PRESET
    controller.get_vertical_swing.return_value = MOCK_VAL_VVANE
    controller.get_horizontal_swing.return_value = MOCK_VAL_HVANE
    controller.get_outdoor_temperature.return_value = MOCK_VAL_OUT_TEMP
    controller.get_heat_power_consumption.return_value = None
    controller.get_cool_power_consumption.return_value = None
    controller.get_rssi.return_value = None
    controller.get_run_hours.return_value = None

    # Commands — already return True (PYINTESISHOME 2.0.1: no change needed here)
    controller.set_power_on = AsyncMock(return_value=True)
    controller.set_power_off = AsyncMock(return_value=True)
    controller.set_temperature = AsyncMock(return_value=True)
    controller.set_mode = AsyncMock(return_value=True)
    controller.set_fan_speed = AsyncMock(return_value=True)
    controller.set_preset_mode = AsyncMock(return_value=True)
    controller.set_vertical_vane = AsyncMock(return_value=True)
    controller.set_horizontal_vane = AsyncMock(return_value=True)

    # Lifecycle
    controller.connect = AsyncMock()
    controller.stop = AsyncMock()
    controller.poll_status = AsyncMock()

    # PYINTESISHOME 1.8.8: add_update_callback is awaited in climate.py
    # PYINTESISHOME 2.0.1: change to MagicMock (sync) and remove `await` in climate.py
    controller.add_update_callback = AsyncMock()
    controller.remove_update_callback = MagicMock()

    with patch(
        "homeassistant.components.intesishome.climate.IntesisHome",
        return_value=controller,
    ):
        yield controller
