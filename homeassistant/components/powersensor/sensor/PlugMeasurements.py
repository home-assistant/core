"""Enum determining what measurements a Powersensor plug can report."""

from enum import Enum


class PlugMeasurements(Enum):
    """Enum to keep track of what measurements plugs can report."""

    WATTS = 1
    VOLTAGE = 2
    APPARENT_CURRENT = 3
    ACTIVE_CURRENT = 4
    REACTIVE_CURRENT = 5
    SUMMATION_ENERGY = 6
    ROLE = 7
