"""Steam constants."""
import logging
from typing import Final

CONF_ACCOUNT = "account"
CONF_ACCOUNTS = "accounts"

DATA_KEY_COORDINATOR = "coordinator"
DEFAULT_NAME = "Steam"
DOMAIN: Final = "steam_online"

LOGGER = logging.getLogger(__package__)

PLACEHOLDERS = {
    "api_key_url": "https://steamcommunity.com/dev/apikey",
    "account_id_url": "https://steamid.io",
}

STATE_OFFLINE = "offline"
STATE_ONLINE = "online"
STATE_BUSY = "busy"
STATE_AWAY = "away"
STATE_SNOOZE = "snooze"
STATE_LOOKING_TO_TRADE = "looking_to_trade"
STATE_LOOKING_TO_PLAY = "looking_to_play"
STEAM_STATUSES = {
    0: STATE_OFFLINE,
    1: STATE_ONLINE,
    2: STATE_BUSY,
    3: STATE_AWAY,
    4: STATE_SNOOZE,
    5: STATE_LOOKING_TO_TRADE,
    6: STATE_LOOKING_TO_PLAY,
}
STEAM_API_URL = "https://steamcdn-a.akamaihd.net/steam/apps/"
STEAM_HEADER_IMAGE_FILE = "header.jpg"
STEAM_MAIN_IMAGE_FILE = "capsule_616x353.jpg"
STEAM_ICON_URL = "https://steamcdn-a.akamaihd.net/steamcommunity/public/images/apps/"
