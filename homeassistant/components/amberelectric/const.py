"""Amber Electric Constants."""

import logging
from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "amberelectric"
CONF_SITE_NAME = "site_name"
CONF_SITE_ID = "site_id"

ATTR_CHANNEL_TYPE = "channel_type"

ATTRIBUTION = "Data provided by Amber Electric"

LOGGER = logging.getLogger(__package__)
PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]

SERVICE_GET_FORECASTS = "get_forecasts"

GENERAL_CHANNEL = "general"
CONTROLLED_LOAD_CHANNEL = "controlled_load"
FEED_IN_CHANNEL = "feed_in"

REQUEST_TIMEOUT = 15
