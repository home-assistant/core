"""Constants for the HomeWizard Energy integration."""
import logging

LOGGER = logging.getLogger(__package__)
DOMAIN = "homewizard_energy"
PLATFORMS = ["sensor", "switch"]

# Device models
MODEL_P1 = "HWE-P1"
MODEL_SDM230 = "SDM230-wifi"
MODEL_SDM630 = "SDM630-wifi"
MODEL_SKT = "HWE-SKT"

# Attributes
ATTR_DATA = "data"
ATTR_STATE = "state"
ATTR_API_VERSION = "api_version"

ATTR_POWER_ON = "power_on"
ATTR_SWITCHLOCK = "switch_lock"
ATTR_BRIGHTNESS = "brightness"

# Config
CONF_API = "api"
CONF_COORDINATOR = "coordinator"
