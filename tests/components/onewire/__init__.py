"""Tests for 1-Wire integration."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from pyownet.protocol import ProtocolError

from .const import ATTR_INJECT_READS, MOCK_OWPROXY_DEVICES


def setup_owproxy_mock_devices(owproxy: MagicMock, device_ids: list[str]) -> None:
    """Set up mock for owproxy."""
    dir_side_effect: dict[str, list] = {}
    read_side_effect: dict[str, list] = {}

    # Setup directory listing
    dir_side_effect["/"] = [[f"/{device_id}/" for device_id in device_ids]]

    for device_id in device_ids:
        _setup_owproxy_mock_device(dir_side_effect, read_side_effect, device_id)

    def _dir(path: str) -> Any:
        if (side_effect := dir_side_effect.get(path)) is None:
            raise NotImplementedError(f"Unexpected _dir call: {path}")
        result = side_effect.pop(0)
        if (
            isinstance(result, Exception)
            or isinstance(result, type)
            and issubclass(result, Exception)
        ):
            raise result
        return result

    def _read(path: str) -> Any:
        if (side_effect := read_side_effect.get(path)) is None:
            raise NotImplementedError(f"Unexpected _read call: {path}")
        if len(side_effect) == 0:
            raise ProtocolError(f"Missing injected value for: {path}")
        result = side_effect.pop(0)
        if (
            isinstance(result, Exception)
            or isinstance(result, type)
            and issubclass(result, Exception)
        ):
            raise result
        return result

    owproxy.return_value.dir.side_effect = _dir
    owproxy.return_value.read.side_effect = _read


def _setup_owproxy_mock_device(
    dir_side_effect: dict[str, list], read_side_effect: dict[str, list], device_id: str
) -> None:
    """Set up mock for owproxy."""
    mock_device = MOCK_OWPROXY_DEVICES[device_id]

    if "branches" in mock_device:
        # Setup branch directory listing
        for branch, branch_details in mock_device["branches"].items():
            sub_dir_side_effect = dir_side_effect.setdefault(
                f"/{device_id}/{branch}", []
            )
            sub_dir_side_effect.append(
                [  # dir on branch
                    f"/{device_id}/{branch}/{sub_device_id}/"
                    for sub_device_id in branch_details
                ]
            )

    _setup_owproxy_mock_device_reads(read_side_effect, mock_device, "/", device_id)

    if "branches" in mock_device:
        for branch, branch_details in mock_device["branches"].items():
            for sub_device_id, sub_device in branch_details.items():
                _setup_owproxy_mock_device_reads(
                    read_side_effect,
                    sub_device,
                    f"/{device_id}/{branch}/",
                    sub_device_id,
                )


def _setup_owproxy_mock_device_reads(
    read_side_effect: dict[str, list], mock_device: Any, root_path: str, device_id: str
) -> None:
    """Set up mock for owproxy."""
    # Setup device reads
    family_read_side_effect = read_side_effect.setdefault(
        f"{root_path}{device_id}/family", []
    )
    family_read_side_effect += [device_id[0:2].encode()]
    if ATTR_INJECT_READS in mock_device:
        for k, v in mock_device[ATTR_INJECT_READS].items():
            device_read_side_effect = read_side_effect.setdefault(
                f"{root_path}{device_id}{k}", []
            )
            device_read_side_effect += v
