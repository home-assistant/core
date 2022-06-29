"""Define constants for the SimpliSafe component."""
import logging

from homeassistant.backports.enum import StrEnum

LOGGER = logging.getLogger(__package__)

DOMAIN = "rainmachine"

CONF_ZONE_RUN_TIME = "zone_run_time"

DATA_CONTROLLER = "controller"
DATA_COORDINATOR = "coordinator"
DATA_PROGRAMS = "programs"
DATA_PROVISION_SETTINGS = "provision.settings"
DATA_RESTRICTIONS_CURRENT = "restrictions.current"
DATA_RESTRICTIONS_UNIVERSAL = "restrictions.universal"
DATA_ZONES = "zones"

DEFAULT_PORT = 8080
DEFAULT_ZONE_RUN = 60 * 10


class RunStates(StrEnum):
    """Define an enum for program/zone run states."""

    NOT_RUNNING = "Not Running"
    QUEUED = "Queued"
    RUNNING = "Running"


RUN_STATE_MAP = {
    0: RunStates.NOT_RUNNING,
    1: RunStates.RUNNING,
    2: RunStates.QUEUED,
}
