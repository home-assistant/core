"""Amber Electric Constants."""

import logging
from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "amberelectric"
CONF_SITE_NAME = "site_name"
CONF_SITE_ID = "site_id"

ATTR_SITE_ID = CONF_SITE_ID
ATTR_CHANNEL_TYPE = "channel_type"

ATTRIBUTION = "Data provided by Amber Electric"

LOGGER = logging.getLogger(__package__)
PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]

GET_FORECASTS_SERVICE = "get_forecasts"
