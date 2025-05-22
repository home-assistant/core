"""Constants for the Playstation Network integration."""

from typing import Final

from psnawp_api.models.trophies import PlatformType

DOMAIN = "playstation_network"
CONF_NPSSO: Final = "npsso"

SUPPORTED_PLATFORMS = {
    PlatformType.PS5,
    PlatformType.PS4,
    PlatformType.PS3,
}
