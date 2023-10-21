"""Constants used by the Withings component."""
import logging

DEFAULT_TITLE = "Withings"
CONF_PROFILES = "profiles"
CONF_USE_WEBHOOK = "use_webhook"

DATA_MANAGER = "data_manager"

CONFIG = "config"
DOMAIN = "withings"
LOG_NAMESPACE = "homeassistant.components.withings"
PROFILE = "profile"
PUSH_HANDLER = "push_handler"

MEASUREMENT_COORDINATOR = "measurement_coordinator"
SLEEP_COORDINATOR = "sleep_coordinator"
BED_PRESENCE_COORDINATOR = "bed_presence_coordinator"
GOALS_COORDINATOR = "goals_coordinator"

LOGGER = logging.getLogger(__package__)


SCORE_POINTS = "points"
UOM_BEATS_PER_MINUTE = "bpm"
UOM_BREATHS_PER_MINUTE = "br/min"
UOM_FREQUENCY = "times"
UOM_MMHG = "mmhg"
