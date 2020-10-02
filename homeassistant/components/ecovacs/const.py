"""Constants for the Ecovacs integration."""
import logging

LOGGER = logging.getLogger(__package__)

DOMAIN = "ecovacs"
PLATFORMS = ["vacuum"]
MANUFACTURER = "ECOVACS ROBOTICS"

CONF_COUNTRY = "country"
CONF_CONTINENT = "continent"
CONF_DEVICE_ID = "device_id"

DEVICES = "devices"
DATA_REMOVE_LISTENER = "remove_listener"

ATTR_ERROR = "error"
ATTR_COMPONENT_PREFIX = "component_"

ECOVACS_ATTR_DEVICE_ID = "did"
ECOVACS_ATTR_NAME = "nick"
