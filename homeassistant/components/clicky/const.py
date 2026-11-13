"""Constants for the Clicky Web Analytics integration."""

from datetime import timedelta
from typing import Final

DOMAIN = "clicky"
UPDATE_INTERVAL: Final = timedelta(minutes=1)
CONF_API_URL = "https://api.clicky.com/api/stats/4"
CONF_SITE_ID: Final = "site_id"
CONF_SITEKEY: Final = "sitekey"
