"""Constants for the iNels integration."""
import logging

from homeassistant.const import Platform

DOMAIN = "inels"

BROKER_CONFIG = "inels_mqtt_broker_config"
BROKER = "inels_mqtt_broker"
COORDINATOR_LIST = "coordinator_list"

CONF_DISCOVERY_PREFIX = "discovery_prefix"

TITLE = "iNELS"
DESCRIPTION = ""
INELS_VERSION = 1
LOGGER = logging.getLogger(__package__)

ICONS = {Platform.SWITCH: "mdi:power-plug"}

MANUAL_SETUP = "manual"

STARTUP_MESSAGE = f"""
-------------------------------------------------------------------
{TITLE}
Version: {INELS_VERSION}
This is a core integration of iNELS system!
-------------------------------------------------------------------
"""
