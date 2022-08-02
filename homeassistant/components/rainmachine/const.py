"""Define constants for the SimpliSafe component."""
from datetime import timedelta
import logging

LOGGER = logging.getLogger(__package__)

DOMAIN = "rainmachine"

CONF_ZONE_RUN_TIME = "zone_run_time"

DATA_PROGRAMS = "programs"
DATA_PROVISION_SETTINGS = "provision.settings"
DATA_RESTRICTIONS_CURRENT = "restrictions.current"
DATA_RESTRICTIONS_UNIVERSAL = "restrictions.universal"
DATA_ZONES = "zones"

DEFAULT_PORT = 8080
DEFAULT_ZONE_RUN = 60 * 10

COORDINATOR_UPDATE_INTERVAL_MAP = {
    DATA_PROVISION_SETTINGS: timedelta(minutes=1),
    DATA_PROGRAMS: timedelta(seconds=30),
    DATA_RESTRICTIONS_CURRENT: timedelta(minutes=1),
    DATA_RESTRICTIONS_UNIVERSAL: timedelta(minutes=1),
    DATA_ZONES: timedelta(seconds=15),
}
