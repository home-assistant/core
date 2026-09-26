"""Constants for the Eufy RoboVac integration."""

from datetime import timedelta
import logging

from homeassistant.const import Platform

DOMAIN = "eufy_robovac"

CONF_LOCAL_KEY = "local_key"
CONF_PROTOCOL_VERSION = "protocol_version"

LOGGER = logging.getLogger(__package__)
PLATFORMS = [Platform.VACUUM]
SCAN_INTERVAL = timedelta(seconds=30)
