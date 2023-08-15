"""Constants for the Fast.com integration."""


import logging

from homeassistant.const import Platform

DOMAIN = "fastdotcom"
DATA_UPDATED = f"{DOMAIN}_data_updated"

LOGGER = logging.getLogger(__package__)

CONF_MANUAL = "manual"

# DEFAULT_INTERVAL = timedelta(hours=1)
DEFAULT_INTERVAL = 0
PLATFORMS: list[Platform] = [Platform.SENSOR]
