"""Types for the ViCare integration."""

from collections.abc import Callable
from dataclasses import dataclass
import enum
from typing import Any

from PyViCare.PyViCareDevice import Device as PyViCareDevice
from PyViCare.PyViCareDeviceConfig import PyViCareDeviceConfig


class HeatingProgram(enum.StrEnum):
    """ViCare preset heating programs.

    As listed in https://github.com/somm15/PyViCare/blob/63f9f7fea505fdf9a26c77c6cd0bff889abcdb05/PyViCare/PyViCareHeatingDevice.py#L606
    """

    COMFORT = "comfort"
    COMFORT_HEATING = "comfortHeating"
    ECO = "eco"
    NORMAL = "normal"
    NORMAL_HEATING = "normalHeating"
    REDUCED = "reduced"
    REDUCED_HEATING = "reducedHeating"
    STANDBY = "standby"


class VentilationMode(enum.StrEnum):
    """ViCare ventilation modes."""

    PERMANENT = "permanent"
    VENTILATION = "ventilation"
    SENSOR_OVERRIDE = "sensorOverride"
    SENSOR_DRIVEN = "sensorDriven"

class VentilationProgram(enum.StrEnum):
    """ViCare preset ventilation programs.

    As listed in https://github.com/somm15/PyViCare/blob/6c5b023ca6c8bb2d38141dd1746dc1705ec84ce8/PyViCare/PyViCareVentilationDevice.py#L37
    """

    # BASIC = "basic"
    # COMFORT = "comfort"
    # INTENSIVE = "intensive"
    # ECO = "eco"
    # STANDARD = "standard"
    # REDUCED = "reduced"
    # STANDBY = "standby"
    LEVEL_ONE = "levelOne"
    LEVEL_TWO = "levelTwo"
    LEVEL_THREE = "levelThree"
    LEVEL_FOUR = "levelFour"
    # PERMANENT = "permanent"
    # SILENT = "silent"

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
