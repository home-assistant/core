"""Constants for the iNels integration."""
import logging

DOMAIN = "inels"

BROKER = "inels_mqtt_broker"
COORDINATOR = "coordinator"
COORDINATOR_LIST = "coordinator_list"

TITLE = "iNELS"
INELS_VERSION = 1
LOGGER = logging.getLogger(__package__)

MANUAL_SETUP = "manual"

STARTUP_MESSAGE = f"""
-------------------------------------------------------------------
{TITLE}
Version: {INELS_VERSION}
This is a core integration of iNELS system!
-------------------------------------------------------------------
"""
