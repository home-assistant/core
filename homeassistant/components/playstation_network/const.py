"""Constants for the Playstation Network integration."""

from enum import StrEnum
from typing import Final

DOMAIN = "playstation_network"
CONF_NPSSO: Final = "npsso"


class PlatformType(StrEnum):
    """PlayStation Platform Enum."""

    PS5 = "PS5"
    PS4 = "PS4"
    PS3 = "PS3"
