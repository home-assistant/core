"""The bluetooth integration."""
from __future__ import annotations

from collections.abc import Mapping
import dataclasses

from homeassistant.helpers import entity


@dataclasses.dataclass
class BluetoothDeviceKey:
    """Key for a bluetooth device.

    Example:
    device_id: outdoor_sensor_1
    key: temperature
    """

    device_id: str | None
    key: str


BluetoothDeviceEntityDescriptionsType = Mapping[
    BluetoothDeviceKey, entity.EntityDescription
]


@dataclasses.dataclass
class BluetoothDescriptionRequiredKeysMixin:
    """Mixin for required keys."""

    device_key: BluetoothDeviceKey
