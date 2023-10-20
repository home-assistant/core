"""Constants for the Lektrico Charging Station integration."""

from logging import Logger, getLogger

from homeassistant.const import Platform

# Integration domain
DOMAIN = "lektrico"

# Logger
LOGGER: Logger = getLogger(__package__)

# List the platforms that charger supports.
CHARGERS_PLATFORMS = [Platform.SENSOR]

# List the platforms that load balancer device supports.
LB_DEVICES_PLATFORMS = [Platform.SENSOR]
