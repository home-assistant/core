"""Define constants for the SimpliSafe component."""
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

# Constants expected by the RainMachine API for Service Data
CONF_CONDITION = "condition"
CONF_DEWPOINT = "dewpoint"
CONF_ET = "et"
CONF_MAXRH = "maxrh"
CONF_MAXTEMP = "maxtemp"
CONF_MINRH = "minrh"
CONF_MINTEMP = "mintemp"
CONF_PRESSURE = "pressure"
CONF_QPF = "qpf"
CONF_RAIN = "rain"
CONF_SECONDS = "seconds"
CONF_SOLARRAD = "solarrad"
CONF_TEMPERATURE = "temperature"
CONF_TIMESTAMP = "timestamp"
CONF_WEATHER = "weather"
CONF_WIND = "wind"
