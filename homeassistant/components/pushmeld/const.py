# homeassistant/components/pushmeld/const.py
"""Constants for the PushMeld integration."""

from typing import Final

DOMAIN: Final = "pushmeld"
DEFAULT_NAME: Final = "PushMeld"
CONF_MAXCODE: Final = "maxcode"
ATTR_DETAILS: Final = "details"
API_URL: Final = "https://api.pushmeld.de/api/v1/notify/"
REQUEST_TIMEOUT: Final = 10.0
DATA_HASS_CONFIG: Final = f"{DOMAIN}_hass_config"
SETUP_ATTEMPT_ID: Final = "setup_attempt_id"
