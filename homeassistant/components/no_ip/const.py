"""Constants for No-IP.com integration."""
from __future__ import annotations

from typing import Final

from homeassistant.const import Platform
from homeassistant.helpers.aiohttp_client import SERVER_SOFTWARE

MANUFACTURER = "No-IP.com"
DOMAIN = "no_ip"
DATA_HASS_CONFIG: Final = "hass_config"
TRACKER_UPDATE_STR: Final = f"{DOMAIN}_tracker_update"

PLATFORMS = [Platform.SENSOR]

# We should set a dedicated address for the user agent.
EMAIL = "hello@home-assistant.io"

DEFAULT_SCAN_INTERVAL = 5

DEFAULT_TIMEOUT = 10

NO_IP_ERRORS = {
    "nohost": "Hostname supplied does not exist under specified account",
    "badauth": "Invalid username password combination",
    "badagent": "Client disabled",
    "!donator": "An update request was sent with a feature that is not available",
    "abuse": "Username is blocked due to abuse",
    "911": "A fatal error on No-IP's side such as a database outage",
}

UPDATE_URL = "https://dynupdate.no-ip.com/nic/update"
HA_USER_AGENT = f"{SERVER_SOFTWARE} {EMAIL}"
