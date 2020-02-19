"""Define constants for the SimpliSafe component."""
from datetime import timedelta
import logging

LOGGER = logging.getLogger(__package__)

DOMAIN = "rainmachine"

DATA_CLIENT = "client"
DATA_PROGRAMS = "programs"
DATA_PROVISION_SETTINGS = "provision.settings"
DATA_RESTRICTIONS_CURRENT = "restrictions.current"
DATA_RESTRICTIONS_UNIVERSAL = "restrictions.universal"
DATA_ZONES = "zones"
DATA_ZONES_DETAILS = "zones_details"

DEFAULT_PORT = 8080
DEFAULT_SCAN_INTERVAL = timedelta(seconds=60)
DEFAULT_SSL = True

PROGRAM_UPDATE_TOPIC = f"{DOMAIN}_program_update"
SENSOR_UPDATE_TOPIC = f"{DOMAIN}_data_update"
ZONE_UPDATE_TOPIC = f"{DOMAIN}_zone_update"
