"""Constants for the Playstation Network integration."""

from typing import Final

from psnawp_api.models.trophies import PlatformType

DOMAIN = "playstation_network"
CONF_NPSSO: Final = "npsso"
CONF_ACCOUNT_ID: Final = "account_id"
CONF_SHOW_ENTITY_PICTURES: Final = "show_entity_pictures"
SUPPORTED_PLATFORMS = {
    PlatformType.PS_VITA,
    PlatformType.PS3,
    PlatformType.PS4,
    PlatformType.PS5,
    PlatformType.PSPC,
}

NPSSO_LINK: Final = "https://ca.account.sony.com/api/v1/ssocookie"
PSN_LINK: Final = "https://playstation.com"
ASSETS_URL: Final = "https://ia600908.us.archive.org/34/items/psn_trophy_images/"
