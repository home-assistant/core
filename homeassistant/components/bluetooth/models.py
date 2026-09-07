"""Models for bluetooth."""

from collections.abc import Callable
from enum import Enum, auto

from home_assistant_bluetooth import BluetoothServiceInfoBleak

BluetoothChange = Enum("BluetoothChange", "ADVERTISEMENT")
type BluetoothCallback = Callable[[BluetoothServiceInfoBleak, BluetoothChange], None]
type ProcessAdvertisementCallback = Callable[[BluetoothServiceInfoBleak], bool]


class BluetoothCallbackReplay(Enum):
    """Controls how history is replayed when a callback is registered."""

    OLDEST_FIRST = auto()
    NEWEST_FIRST = auto()
    DISABLED = auto()
