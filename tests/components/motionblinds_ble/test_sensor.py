"""Tests for Motionblinds BLE sensors."""

from collections.abc import Callable
from typing import Any

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
    DOMAIN,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from . import setup_platform


@pytest.mark.parametrize(
    ("sensor", "update_func", "initial_value", "args", "expected_value"),
    [
        (
            "connection_status",
            lambda device: device.update_connection,
            MotionConnectionType.DISCONNECTED.value,
            [MotionConnectionType.CONNECTING],
            MotionConnectionType.CONNECTING.value,
        ),
        (
            ATTR_BATTERY,
            lambda device: device.update_battery,
            "unknown",
            [25, True, False],
            "25",
        ),
        (  # Battery unknown
            ATTR_BATTERY,
            lambda device: device.update_battery,
            "unknown",
            [None, False, False],
            "unknown",
        ),
        (  # Wired
            ATTR_BATTERY,
            lambda device: device.update_battery,
            "unknown",
            [255, False, True],
            "255",
        ),
        (  # Almost full
            ATTR_BATTERY,
            lambda device: device.update_battery,
            "unknown",
            [99, False, False],
            "99",
        ),
        (  # Almost empty
            ATTR_BATTERY,
            lambda device: device.update_battery,
            "unknown",
            [1, False, False],
            "1",
        ),
        (
            "calibration_status",
            lambda device: device.update_calibration,
            "unknown",
            [MotionCalibrationType.CALIBRATING],
            MotionCalibrationType.CALIBRATING.value,
        ),
        (
            ATTR_SIGNAL_STRENGTH,
            lambda device: device.update_signal_strength,
            "unknown",
            [-50],
            "-50",
        ),
    ],
)
async def test_sensor(
    hass: HomeAssistant,
    sensor: str,
    update_func: Callable[[MotionDevice], Callable[..., None]],
    initial_value: str,
    args: list[Any],
    expected_value: str,
) -> None:
    """Test sensors."""

    config_entry, name = await setup_platform(
        hass, [Platform.SENSOR], blind_type=MotionBlindType.CURTAIN
    )
    device: MotionDevice = hass.data[DOMAIN][config_entry.entry_id]

    assert hass.states.get(f"{SENSOR_DOMAIN}.{name}_{sensor}").state == initial_value
    update_func(device)(*args)
    assert hass.states.get(f"{SENSOR_DOMAIN}.{name}_{sensor}").state == expected_value

    await hass.async_block_till_done()
