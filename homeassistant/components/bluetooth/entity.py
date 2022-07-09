"""The bluetooth integration."""

import dataclasses

from .device import BluetoothDeviceKey


@dataclasses.dataclass
class BluetoothDescriptionRequiredKeysMixin:
    """Mixin for required keys."""

    device_key: BluetoothDeviceKey
