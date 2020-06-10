"""Constants for the Toon integration."""
from datetime import timedelta

DOMAIN = "toon"

DATA_TOON = "toon"
DATA_TOON_CLIENT = "toon_client"
DATA_TOON_CONFIG = "toon_config"
DATA_TOON_UPDATED = "toon_updated"

CONF_DISPLAY = "display"
CONF_TENANT = "tenant"

DEFAULT_SCAN_INTERVAL = timedelta(seconds=300)
DEFAULT_MAX_TEMP = 30.0
DEFAULT_MIN_TEMP = 6.0

CURRENCY_EUR = "EUR"
VOLUME_CM3 = "CM3"
VOLUME_M3 = "M3"
