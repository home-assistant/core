"""Constants for the Fronius integration."""
from typing import Final, TypedDict

DOMAIN: Final = "fronius"

SolarNetId = str
SOLAR_NET_ID_SYSTEM: SolarNetId = "system"


class FroniusConfigEntryData(TypedDict):
    """ConfigEntry for the Fronius integration."""

    host: str
    is_logger: bool
