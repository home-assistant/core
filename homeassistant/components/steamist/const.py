"""Constants for the Steamist integration."""

import aiohttp
from discovery30303 import Device30303

from homeassistant.util.hass_dict import HassKey

DOMAIN = "steamist"

CONNECTION_EXCEPTIONS = (TimeoutError, aiohttp.ClientError)

STARTUP_SCAN_TIMEOUT = 5
DISCOVER_SCAN_TIMEOUT = 10

DATA_DISCOVERY: HassKey[list[Device30303]] = HassKey(DOMAIN)
