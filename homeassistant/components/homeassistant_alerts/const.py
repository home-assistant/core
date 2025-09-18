"""Constants for the Home Assistant alerts integration."""

from datetime import timedelta

import aiohttp

COMPONENT_LOADED_COOLDOWN = 30
DOMAIN = "homeassistant_alerts"
UPDATE_INTERVAL = timedelta(hours=3)

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30)
