"""Constants for the LinknLink integration."""

from datetime import timedelta
import logging

DOMAIN = "linknlink"
DISPLAY_MODEL = "eMotion Ultra"

DEFAULT_PORT = 80
POSITION_SUBSCRIPTION_CONFIRM_TIMEOUT = 60.0
ENVIRONMENT_UPDATE_INTERVAL = timedelta(seconds=30)

LOGGER = logging.getLogger(__package__)
