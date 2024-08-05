"""Models for bluetooth."""

from __future__ import annotations

from collections.abc import Callable
from enum import Enum

from home_assistant_bluetooth import BluetoothServiceInfoBleak

BluetoothChange = Enum("BluetoothChange", "ADVERTISEMENT")
type BluetoothCallback = Callable[[BluetoothServiceInfoBleak, BluetoothChange], None]
type ProcessAdvertisementCallback = Callable[[BluetoothServiceInfoBleak], bool]
