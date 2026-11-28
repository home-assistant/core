"""Constants for the EDL21 component."""

import logging

LOGGER = logging.getLogger(__package__)

DOMAIN = "edl21"

CONF_SERIAL_PORT = "serial_port"

CONF_UPDATE_INTERVAL = "update_interval"

DEFAULT_UPDATE_INTERVAL = 0

CONF_LIMIT_INTERVAL = "limit_interval"

DEFAULT_LIMITED_UPDATE_INTERVAL = 60

MAX_UPDATE_INTERVAL = 3600

SIGNAL_EDL21_TELEGRAM = "edl21_telegram"

DEFAULT_TITLE = "Smart Meter"

DEFAULT_DEVICE_NAME = "Smart Meter"
