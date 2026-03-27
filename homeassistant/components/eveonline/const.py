"""Constants for the Eve Online integration."""

from typing import Final

DOMAIN: Final = "eveonline"

OAUTH2_AUTHORIZE: Final = "https://login.eveonline.com/v2/oauth/authorize"
OAUTH2_TOKEN: Final = "https://login.eveonline.com/v2/oauth/token"

SCOPES: Final[list[str]] = [
    "esi-characters.read_fatigue.v1",
    "esi-industry.read_character_jobs.v1",
    "esi-location.read_location.v1",
    "esi-location.read_online.v1",
    "esi-location.read_ship_type.v1",
    "esi-mail.read_mail.v1",
    "esi-markets.read_character_orders.v1",
    "esi-skills.read_skillqueue.v1",
    "esi-skills.read_skills.v1",
    "esi-wallet.read_character_wallet.v1",
]
