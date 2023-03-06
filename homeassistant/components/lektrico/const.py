"""Constants for the Lektrico Charging Station integration."""

from logging import Logger, getLogger

from homeassistant.const import Platform

# Integration domain
DOMAIN = "lektrico"

# Services
SERVICE_IDENTIFY = "identify"

# Logger
LOGGER: Logger = getLogger(__package__)

# List the platforms that charger supports.
CHARGERS_PLATFORMS = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SWITCH,
]

# List the platforms that load balancer device supports.
LB_DEVICES_PLATFORMS = [
    Platform.SENSOR,
    Platform.BUTTON,
    Platform.SELECT,
]
