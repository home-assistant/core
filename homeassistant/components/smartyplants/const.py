"""Constants for the SmartyPlants integration."""

from datetime import timedelta
from typing import Final

DOMAIN: Final = "smartyplants"

DEFAULT_HOST: Final = "https://api.smartyplants.ai"

# Poll interval used as the baseline. Webhook pushes land in between and keep
# the data fresher than this without changing the fallback cadence. The
# backend caches each account's payload and answers unchanged polls with a
# 304, so a poll that finds nothing new is cheap.
DEFAULT_SCAN_INTERVAL: Final = timedelta(minutes=1)

CONF_WEBHOOK_SECRET: Final = "webhook_secret"

SIGNATURE_HEADER: Final = "X-Smartyplants-Signature"

MANUFACTURER: Final = "SmartyPlants"
MODEL: Final = "Plant Sensor"
