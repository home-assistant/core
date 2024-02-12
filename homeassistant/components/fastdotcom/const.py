"""Constants for the Fast.com integration."""
import logging

from homeassistant.const import Platform

LOGGER = logging.getLogger(__package__)

DOMAIN = "fastdotcom"
DATA_UPDATED = f"{DOMAIN}_data_updated"

CONF_MANUAL = "manual"

SERVICE_NAME = "speedtest"

DEFAULT_NAME = "Fast.com"
DEFAULT_INTERVAL = 1
PLATFORMS: list[Platform] = [Platform.SENSOR]
