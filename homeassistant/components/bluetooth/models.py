"""Models for bluetooth."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Final

from bleak import BaseBleakClient
from bluetooth_data_tools import monotonic_time_coarse
from home_assistant_bluetooth import BluetoothServiceInfoBleak

if TYPE_CHECKING:
    from .manager import BluetoothManager


MANAGER: BluetoothManager | None = None

MONOTONIC_TIME: Final = monotonic_time_coarse


@dataclass(slots=True)
class HaBluetoothConnector:
    """Data for how to connect a BLEDevice from a given scanner."""

    client: type[BaseBleakClient]
    source: str
    can_connect: Callable[[], bool]


class BluetoothScanningMode(Enum):
    """The mode of scanning for bluetooth devices."""

    PASSIVE = "passive"
    ACTIVE = "active"


BluetoothChange = Enum("BluetoothChange", "ADVERTISEMENT")
BluetoothCallback = Callable[[BluetoothServiceInfoBleak, BluetoothChange], None]
ProcessAdvertisementCallback = Callable[[BluetoothServiceInfoBleak], bool]
