"""Constants for the Eve Online integration."""

from typing import Final

DOMAIN: Final = "eveonline"

CONF_CHARACTER_ID: Final = "character_id"
CONF_CHARACTER_NAME: Final = "character_name"

OAUTH2_AUTHORIZE: Final = "https://login.eveonline.com/v2/oauth/authorize"
OAUTH2_TOKEN: Final = "https://login.eveonline.com/v2/oauth/token"

SCOPES: Final[list[str]] = [
    "esi-location.read_location.v1",
    "esi-location.read_ship_type.v1",
    "esi-wallet.read_character_wallet.v1",
]
