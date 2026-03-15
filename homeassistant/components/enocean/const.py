"""Constants for the EnOcean integration."""

import logging

from homeassistant.const import Platform

DOMAIN = "enocean"

MANUFACTURER = "EnOcean"

CONFIG_FLOW_VERSION = 1
CONFIG_FLOW_MINOR_VERSION = 2

ERROR_INVALID_DONGLE_PATH = "invalid_dongle_path"

SIGNAL_RECEIVE_MESSAGE = "enocean.receive_message"
SIGNAL_SEND_MESSAGE = "enocean.send_message"

LOGGER = logging.getLogger(__package__)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.LIGHT,
    Platform.SENSOR,
    Platform.SWITCH,
]
