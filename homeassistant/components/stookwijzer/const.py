"""Constants for the Stookwijzer integration."""
from enum import StrEnum
import logging
from typing import Final

DOMAIN: Final = "stookwijzer"
LOGGER = logging.getLogger(__package__)


class StookwijzerState(StrEnum):
    """Stookwijzer states for sensor entity."""

    BLUE = "blauw"
    ORANGE = "oranje"
    RED = "rood"
