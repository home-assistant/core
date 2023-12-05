"""Models for bluetooth."""
from __future__ import annotations

from collections.abc import Callable
from enum import Enum
from typing import TYPE_CHECKING, Final

from bluetooth_data_tools import monotonic_time_coarse
from home_assistant_bluetooth import BluetoothServiceInfoBleak

if TYPE_CHECKING:
    from .manager import BluetoothManager


MANAGER: BluetoothManager | None = None

MONOTONIC_TIME: Final = monotonic_time_coarse


class BluetoothScanningMode(Enum):
    """The mode of scanning for bluetooth devices."""

    PASSIVE = "passive"
    ACTIVE = "active"


BluetoothChange = Enum("BluetoothChange", "ADVERTISEMENT")
BluetoothCallback = Callable[[BluetoothServiceInfoBleak, BluetoothChange], None]
ProcessAdvertisementCallback = Callable[[BluetoothServiceInfoBleak], bool]
