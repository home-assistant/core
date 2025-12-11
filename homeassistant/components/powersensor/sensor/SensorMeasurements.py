"""Enum determining what measurements a Powersensor sensor can report."""

from enum import Enum


class SensorMeasurements(Enum):
    """Enum to keep track of what measurements sensors can report."""

    Battery = 1
    WATTS = 2
    SUMMATION_ENERGY = 3
    ROLE = 4
    RSSI = 5
