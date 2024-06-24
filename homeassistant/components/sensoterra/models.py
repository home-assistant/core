"""Sensoterra models."""

from enum import StrEnum, auto
from typing import NamedTuple

from sensoterra.probe import Probe, Sensor


class ProbeSensorType(StrEnum):
    """Generic sensors within a Sensoterra probe."""

    MOISTURE = auto()
    SI = auto()
    TEMPERATURE = auto()
    BATTERY = auto()
    RSSI = auto()


class SensoterraSensor(NamedTuple):
    """Encapsulate a sensor of a Sensoterra Probe."""

    probe: Probe
    sensor: Sensor
