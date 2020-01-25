"""Define constants for the SimpliSafe component."""
from datetime import timedelta
import logging

LOGGER = logging.getLogger(__package__)

DOMAIN = "rainmachine"

DATA_CLIENT = "client"

DEFAULT_PORT = 8080
DEFAULT_SCAN_INTERVAL = timedelta(seconds=60)
DEFAULT_SSL = True

PROVISION_SETTINGS = "provision.settings"
RESTRICTIONS_CURRENT = "restrictions.current"
RESTRICTIONS_UNIVERSAL = "restrictions.universal"

PROGRAM_UPDATE_TOPIC = f"{DOMAIN}_program_update"
SENSOR_UPDATE_TOPIC = f"{DOMAIN}_data_update"
ZONE_UPDATE_TOPIC = f"{DOMAIN}_zone_update"
