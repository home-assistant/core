"""Models for bluetooth."""
from __future__ import annotations

from collections.abc import Callable
from enum import Enum
from typing import TYPE_CHECKING

from home_assistant_bluetooth import BluetoothServiceInfoBleak

if TYPE_CHECKING:
    from .manager import HomeAssistantBluetoothManager


MANAGER: HomeAssistantBluetoothManager | None = None


BluetoothChange = Enum("BluetoothChange", "ADVERTISEMENT")
BluetoothCallback = Callable[[BluetoothServiceInfoBleak, BluetoothChange], None]
ProcessAdvertisementCallback = Callable[[BluetoothServiceInfoBleak], bool]
