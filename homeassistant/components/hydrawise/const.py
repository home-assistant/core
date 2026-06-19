"""Constants for the Hydrawise integration."""

from datetime import timedelta
import logging

from homeassistant.const import __version__ as HA_VERSION

LOGGER = logging.getLogger(__package__)

APP_ID = f"homeassistant-{HA_VERSION}"

DOMAIN = "hydrawise"
DEFAULT_WATERING_TIME = timedelta(minutes=15)

MANUFACTURER = "Hydrawise"
MODEL_ZONE = "Zone"

MAIN_SCAN_INTERVAL = timedelta(minutes=5)
WATER_USE_SCAN_INTERVAL = timedelta(minutes=60)

CONF_GQL_TOKENS_PER_EPOCH = "gql_tokens_per_epoch"
# pydrawise's HybridClient throttles GraphQL calls to a number of "tokens" per
# 30-minute epoch (default: 5) to stay within the Hydrawise cloud rate limit.
# Accounts with several controllers or zones can exhaust that budget, leaving
# data stale, so the limit is exposed as an option.
GQL_THROTTLE_EPOCH = timedelta(minutes=30)
DEFAULT_GQL_TOKENS_PER_EPOCH = 5

SIGNAL_UPDATE_HYDRAWISE = "hydrawise_update"

SERVICE_RESUME = "resume"
SERVICE_START_WATERING = "start_watering"
SERVICE_SUSPEND = "suspend"

ATTR_DURATION = "duration"
ATTR_UNTIL = "until"
