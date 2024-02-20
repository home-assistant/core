"""Types for the ViCare integration."""
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from PyViCare.PyViCareDevice import Device as PyViCareDevice
from PyViCare.PyViCareDeviceConfig import PyViCareDeviceConfig


@dataclass(frozen=True)
class ViCareDevice:
    """Dataclass holding the device api and config."""

    config: PyViCareDeviceConfig
    api: PyViCareDevice


@dataclass(frozen=True)
class ViCareRequiredKeysMixin:
    """Mixin for required keys."""

    value_getter: Callable[[PyViCareDevice], Any]


@dataclass(frozen=True)
class ViCareRequiredKeysMixinWithSet(ViCareRequiredKeysMixin):
    """Mixin for required keys with setter."""

    value_setter: Callable[[PyViCareDevice], bool]
