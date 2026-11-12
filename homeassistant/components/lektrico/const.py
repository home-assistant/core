"""Constants for the Lektrico Charging Station integration."""

from logging import Logger, getLogger

# Integration domain
DOMAIN = "lektrico"

CONF_HW_VERSION = "hw_version"
CONF_SERIAL_NUMBER = "serial_number"

# Logger
LOGGER: Logger = getLogger(__package__)
