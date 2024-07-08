"""Types for the ViCare integration."""

from collections.abc import Callable
from dataclasses import dataclass
import enum
from typing import Any

from PyViCare.PyViCareDevice import Device as PyViCareDevice
from PyViCare.PyViCareDeviceConfig import PyViCareDeviceConfig

from homeassistant.components.climate import (
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_HOME,
    PRESET_SLEEP,
)


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

    @staticmethod
    def to_ha_preset(program: str) -> str | None:
        """Return the mapped Home Assistant preset for the ViCare heating program."""

        try:
            heating_program = HeatingProgram(program)
        except ValueError:
            # ignore unsupported / unmapped programs
            return None
        return VICARE_TO_HA_PRESET_HEATING.get(heating_program) if program else None

    @staticmethod
    def from_ha_preset(
        ha_preset: str, supported_heating_programs: list[str]
    ) -> str | None:
        """Return the mapped ViCare heating program for the Home Assistant preset."""
        for program in supported_heating_programs:
            if VICARE_TO_HA_PRESET_HEATING.get(HeatingProgram(program)) == ha_preset:
                return program
        return None


VICARE_TO_HA_PRESET_HEATING = {
    HeatingProgram.COMFORT: PRESET_COMFORT,
    HeatingProgram.COMFORT_HEATING: PRESET_COMFORT,
    HeatingProgram.ECO: PRESET_ECO,
    HeatingProgram.NORMAL: PRESET_HOME,
    HeatingProgram.NORMAL_HEATING: PRESET_HOME,
    HeatingProgram.REDUCED: PRESET_SLEEP,
    HeatingProgram.REDUCED_HEATING: PRESET_SLEEP,
}


class VentilationMode(enum.StrEnum):
    """ViCare ventilation modes."""

    PERMANENT = "permanent"  # on, speed controlled by program (levelOne-levelFour)
    VENTILATION = "ventilation"  # activated by schedule
    SENSOR_DRIVEN = "sensor_driven"  # activated by schedule, override by sensor
    SENSOR_OVERRIDE = "sensor_override"  # activated by sensor

    @staticmethod
    def to_vicare_mode(mode: str | None) -> str | None:
        """Return the mapped ViCare ventilation mode for the Home Assistant mode."""
        if mode:
            try:
                ventilation_mode = VentilationMode(mode)
            except ValueError:
                # ignore unsupported / unmapped modes
                return None
            return HA_TO_VICARE_MODE_VENTILATION.get(ventilation_mode) if mode else None
        return None

    @staticmethod
    def from_vicare_mode(vicare_mode: str | None) -> str | None:
        """Return the mapped Home Assistant mode for the ViCare ventilation mode."""
        for mode in VentilationMode:
            if HA_TO_VICARE_MODE_VENTILATION.get(VentilationMode(mode)) == vicare_mode:
                return mode
        return None


HA_TO_VICARE_MODE_VENTILATION = {
    VentilationMode.PERMANENT: "permanent",
    VentilationMode.VENTILATION: "ventilation",
    VentilationMode.SENSOR_DRIVEN: "sensorDriven",
    VentilationMode.SENSOR_OVERRIDE: "sensorOverride",
}


class VentilationProgram(enum.StrEnum):
    """ViCare preset ventilation programs.

    As listed in https://github.com/somm15/PyViCare/blob/6c5b023ca6c8bb2d38141dd1746dc1705ec84ce8/PyViCare/PyViCareVentilationDevice.py#L37
    """

    LEVEL_ONE = "levelOne"
    LEVEL_TWO = "levelTwo"
    LEVEL_THREE = "levelThree"
    LEVEL_FOUR = "levelFour"


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
