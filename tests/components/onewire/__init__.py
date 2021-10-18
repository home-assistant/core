"""Tests for 1-Wire integration."""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from pyownet.protocol import ProtocolError

from homeassistant.components.onewire.const import DEFAULT_SYSBUS_MOUNT_DIR

from .const import MOCK_OWPROXY_DEVICES, MOCK_SYSBUS_DEVICES


def setup_owproxy_mock_devices(
    owproxy: MagicMock, platform: str, device_ids: list(str)
) -> None:
    """Set up mock for owproxy."""
    dir_return_value = []
    main_read_side_effect = []
    sub_read_side_effect = []

    for device_id in device_ids:
        mock_device = MOCK_OWPROXY_DEVICES[device_id]

        # Setup directory listing
        dir_return_value += [f"/{device_id}/"]

        # Setup device reads
        main_read_side_effect += [device_id[0:2].encode()]
        if "inject_reads" in mock_device:
            main_read_side_effect += mock_device["inject_reads"]

        # Setup sub-device reads
        device_sensors = mock_device.get(platform, [])
        for expected_sensor in device_sensors:
            sub_read_side_effect.append(expected_sensor["injected_value"])

    # Ensure enough read side effect
    read_side_effect = (
        main_read_side_effect
        + sub_read_side_effect
        + [ProtocolError("Missing injected value")] * 20
    )
    owproxy.return_value.dir.return_value = dir_return_value
    owproxy.return_value.read.side_effect = read_side_effect


def setup_sysbus_mock_devices(
    platform: str, device_ids: list[str]
) -> tuple[list[str], list[Any]]:
    """Set up mock for sysbus."""
    glob_result = []
    read_side_effect = []

    for device_id in device_ids:
        mock_device = MOCK_SYSBUS_DEVICES[device_id]

        # Setup directory listing
        glob_result += [f"/{DEFAULT_SYSBUS_MOUNT_DIR}/{device_id}"]

        # Setup sub-device reads
        device_sensors = mock_device.get(platform, [])
        for expected_sensor in device_sensors:
            if isinstance(expected_sensor["injected_value"], list):
                read_side_effect += expected_sensor["injected_value"]
            else:
                read_side_effect.append(expected_sensor["injected_value"])

    # Ensure enough read side effect
    read_side_effect.extend([FileNotFoundError("Missing injected value")] * 20)

    return (glob_result, read_side_effect)
