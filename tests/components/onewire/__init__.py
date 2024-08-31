"""Tests for 1-Wire integration."""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from pyownet.protocol import ProtocolError

from homeassistant.const import Platform

from .const import ATTR_INJECT_READS, MOCK_OWPROXY_DEVICES


def setup_owproxy_mock_devices(
    owproxy: MagicMock, platform: Platform, device_ids: list[str]
) -> None:
    """Set up mock for owproxy."""
    main_dir_return_value = []
    sub_dir_side_effect = []
    main_read_side_effect = []
    sub_read_side_effect = []

    for device_id in device_ids:
        _setup_owproxy_mock_device(
            main_dir_return_value,
            sub_dir_side_effect,
            main_read_side_effect,
            sub_read_side_effect,
            device_id,
            platform,
        )

    # Ensure enough read side effect
    dir_side_effect = [main_dir_return_value] + sub_dir_side_effect
    read_side_effect = (
        main_read_side_effect
        + sub_read_side_effect
        + [ProtocolError("Missing injected value")] * 20
    )
    owproxy.return_value.dir.side_effect = dir_side_effect
    owproxy.return_value.read.side_effect = read_side_effect


def _setup_owproxy_mock_device(
    main_dir_return_value: list,
    sub_dir_side_effect: list,
    main_read_side_effect: list,
    sub_read_side_effect: list,
    device_id: str,
    platform: Platform,
) -> None:
    """Set up mock for owproxy."""
    mock_device = MOCK_OWPROXY_DEVICES[device_id]

    # Setup directory listing
    main_dir_return_value += [f"/{device_id}/"]
    if "branches" in mock_device:
        # Setup branch directory listing
        for branch, branch_details in mock_device["branches"].items():
            sub_dir_side_effect.append(
                [  # dir on branch
                    f"/{device_id}/{branch}/{sub_device_id}/"
                    for sub_device_id in branch_details
                ]
            )

    _setup_owproxy_mock_device_reads(
        main_read_side_effect,
        sub_read_side_effect,
        mock_device,
        device_id,
        platform,
    )

    if "branches" in mock_device:
        for branch_details in mock_device["branches"].values():
            for sub_device_id, sub_device in branch_details.items():
                _setup_owproxy_mock_device_reads(
                    main_read_side_effect,
                    sub_read_side_effect,
                    sub_device,
                    sub_device_id,
                    platform,
                )


def _setup_owproxy_mock_device_reads(
    main_read_side_effect: list,
    sub_read_side_effect: list,
    mock_device: Any,
    device_id: str,
    platform: Platform,
) -> None:
    """Set up mock for owproxy."""
    # Setup device reads
    main_read_side_effect += [device_id[0:2].encode()]
    if ATTR_INJECT_READS in mock_device:
        main_read_side_effect += mock_device[ATTR_INJECT_READS]

    # Setup sub-device reads
    device_sensors = mock_device.get(platform, [])
    if platform is Platform.SENSOR and device_id.startswith("12"):
        # We need to check if there is TAI8570 plugged in
        for expected_sensor in device_sensors:
            sub_read_side_effect.append(expected_sensor[ATTR_INJECT_READS])
    for expected_sensor in device_sensors:
        sub_read_side_effect.append(expected_sensor[ATTR_INJECT_READS])
