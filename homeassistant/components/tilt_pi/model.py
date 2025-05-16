"""Models for Tilt Pi."""

from dataclasses import dataclass
from enum import StrEnum


class TiltColor(StrEnum):
    """Tilt color options."""

    BLUE = "Blue"
    BLACK = "Black"
    RED = "Red"
    GREEN = "Green"
    ORANGE = "Orange"
    YELLOW = "Yellow"
    PURPLE = "Purple"
    PINK = "Pink"


@dataclass
class TiltHydrometerData:
    """Data for a Tilt Hydrometer."""

    mac_id: str
    color: TiltColor
    temperature: float
    gravity: float
