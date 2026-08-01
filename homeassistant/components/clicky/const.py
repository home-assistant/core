"""Constants for the Clicky Web Analytics integration."""

from typing import Final

DOMAIN = "clicky"
CONF_API_URL = "https://api.clicky.com/api/stats/4"
CONF_NICKNAME: Final = "nickname"
CONF_SITE_ID: Final = "site_id"
CONF_SITEKEY: Final = "sitekey"

METRICS = {
    "visitorsOnline": "visitors-online",
    "timeTotal": "time-total",
}
