"""Constants for the Toon integration."""

from datetime import timedelta

DOMAIN = "toon"

CONF_AGREEMENT = "agreement"
CONF_AGREEMENT_ID = "agreement_id"
CONF_CLOUDHOOK_URL = "cloudhook_url"
CONF_MIGRATE = "migrate"

DEFAULT_SCAN_INTERVAL = timedelta(seconds=300)
DEFAULT_MAX_TEMP = 30.0
DEFAULT_MIN_TEMP = 6.0

CURRENCY_EUR = "EUR"
VOLUME_CM3 = "CM3"
VOLUME_LHOUR = "L/H"
VOLUME_LMIN = "L/MIN"
