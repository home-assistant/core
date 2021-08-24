"""Define constants for the SimpliSafe component."""
from dataclasses import dataclass
import logging

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


@dataclass
class RainMachineSensorDescriptionMixin:
    """Define an entity description mixin for binary and regular sensors."""

    api_category: str
