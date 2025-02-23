"""Models for Tilt Pi."""

from dataclasses import dataclass
from enum import StrEnum


class TiltColor(StrEnum):
    """Tilt color options."""

    RED = "red"
    GREEN = "green"
    BLACK = "black"
    PURPLE = "purple"
    ORANGE = "orange"
    BLUE = "blue"
    YELLOW = "yellow"
    PINK = "pink"


@dataclass
class TiltHydrometerData:
    """Data for a Tilt Hydrometer."""

    mac_id: str
    color: TiltColor
    temperature: float
    gravity: float
