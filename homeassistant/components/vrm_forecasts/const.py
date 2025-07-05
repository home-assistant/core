"""Constants for the Victron VRM Solar Forecast integration."""

import logging

DOMAIN = "vrm_forecasts"
LOGGER = logging.getLogger(__package__)

CONF_SITE_ID = "site_id"
CONF_API_KEY = "api_key"

BASE_URL = "https://vrmapi.victronenergy.com/v2"
