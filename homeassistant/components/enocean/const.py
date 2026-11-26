"""Constants for the EnOcean integration."""

import logging

from homeassistant.const import Platform

DOMAIN = "enocean"

MANUFACTURER = "EnOcean"

ERROR_INVALID_DEVICE_ID = "invalid_device_id"
ERROR_INVALID_DONGLE_PATH = "invalid_dongle_path"

CONF_DEVICE_TYPE_ID = "device_type_id"

SUBENTRY_TYPE_DEVICE = "device"

# Device types of the enocean-async library
DEVICE_TYPE_ROCKER_SWITCH = "EEP/F6-02-01"

SIGNAL_DEVICE_ADDED = "enocean.device_added"
SIGNAL_RECEIVE_MESSAGE = "enocean.receive_message"
SIGNAL_SEND_MESSAGE = "enocean.send_message"

LOGGER = logging.getLogger(__package__)

# Platforms set up from the config entry. The other platforms still read YAML.
PLATFORMS = [Platform.BINARY_SENSOR]
