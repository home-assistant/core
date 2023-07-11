"""Constants for the Stookwijzer integration."""
import logging
from typing import Final

from homeassistant.backports.enum import StrEnum

DOMAIN: Final = "stookwijzer"
LOGGER = logging.getLogger(__package__)


class StookwijzerState(StrEnum):
    """Stookwijzer states for sensor entity."""

    BLUE = "blauw"
    ORANGE = "oranje"
    RED = "rood"
