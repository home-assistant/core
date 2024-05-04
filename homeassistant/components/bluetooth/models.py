"""Models for bluetooth."""

from __future__ import annotations

from collections.abc import Callable
from enum import Enum

from home_assistant_bluetooth import BluetoothServiceInfoBleak

BluetoothChange = Enum("BluetoothChange", "ADVERTISEMENT")
BluetoothCallback = Callable[[BluetoothServiceInfoBleak, BluetoothChange], None]
ProcessAdvertisementCallback = Callable[[BluetoothServiceInfoBleak], bool]
