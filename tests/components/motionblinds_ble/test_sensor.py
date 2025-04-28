"""Tests for Motionblinds BLE sensors."""

from collections.abc import Callable
from typing import Any
from unittest.mock import Mock

from motionblindsble.const import (
    MotionBlindType,
    MotionCalibrationType,
    MotionConnectionType,
)
from motionblindsble.device import MotionDevice
import pytest

from homeassistant.components.motionblinds_ble.const import (
    ATTR_BATTERY,
    ATTR_SIGNAL_STRENGTH,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize("blind_type", [MotionBlindType.CURTAIN])
@pytest.mark.parametrize(
    ("sensor", "register_callback", "initial_value", "args", "expected_value"),
    [
        (
            "connection_status",
            lambda device: device.register_connection_callback,
            MotionConnectionType.DISCONNECTED.value,
            [MotionConnectionType.CONNECTING],
            MotionConnectionType.CONNECTING.value,
        ),
        (
            ATTR_BATTERY,
            lambda device: device.register_battery_callback,
            "unknown",
            [25, True, False],
            "25",
        ),
        (  # Battery unknown
            ATTR_BATTERY,
            lambda device: device.register_battery_callback,
            "unknown",
            [None, False, False],
            "unknown",
        ),
        (  # Wired
            ATTR_BATTERY,
            lambda device: device.register_battery_callback,
            "unknown",
            [255, False, True],
            "255",
        ),
        (  # Almost full
            ATTR_BATTERY,
            lambda device: device.register_battery_callback,
            "unknown",
            [99, False, False],
            "99",
        ),
        (  # Almost empty
            ATTR_BATTERY,
            lambda device: device.register_battery_callback,
            "unknown",
            [1, False, False],
            "1",
        ),
        (
            "calibration_status",
            lambda device: device.register_calibration_callback,
            "unknown",
            [MotionCalibrationType.CALIBRATING],
            MotionCalibrationType.CALIBRATING.value,
        ),
        (
            ATTR_SIGNAL_STRENGTH,
            lambda device: device.register_signal_strength_callback,
            "unknown",
            [-50],
            "-50",
        ),
    ],
)
async def test_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_motion_device: Mock,
    name: str,
    sensor: str,
    register_callback: Callable[[MotionDevice], Callable[..., None]],
    initial_value: str,
    args: list[Any],
    expected_value: str,
) -> None:
    """Test sensors."""

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(f"{SENSOR_DOMAIN}.{name}_{sensor}").state == initial_value
    update_func = register_callback(mock_motion_device).call_args[0][0]
    update_func(*args)
    assert hass.states.get(f"{SENSOR_DOMAIN}.{name}_{sensor}").state == expected_value
