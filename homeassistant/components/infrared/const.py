"""Constants for the Infrared integration."""

from enum import IntFlag
from typing import Final

DOMAIN: Final = "infrared"


class InfraredEntityFeature(IntFlag):
    """Supported features of infrared entities."""

    TRANSMIT = 1
    """Entity can transmit IR signals."""

    RECEIVE = 2
    """Entity can receive/learn IR signals."""
