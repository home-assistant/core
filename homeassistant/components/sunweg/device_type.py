"""The Sun WEG device type."""
from enum import Enum


class DeviceType(Enum):
    """Device Type Enum."""

    TOTAL = 1
    INVERTER = 2
    PHASE = 3
    STRING = 4
