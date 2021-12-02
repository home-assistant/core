"""Constants for Radarr."""
import logging

from homeassistant.const import DATA_GIGABYTES

LOGGER = logging.getLogger(__name__)


DOMAIN = "radarr"

# Config Keys
CONF_BASE_PATH = "base_path"
CONF_UPCOMING_DAYS = "upcoming_days"
CONF_DAYS = "days"
CONF_INCLUDED = "include_paths"
CONF_UNIT = "unit"
CONF_URLBASE = "urlbase"

DEFAULT_DAYS = "1"
DEFAULT_HOST = "localhost"
DEFAULT_NAME = "Radarr"
DEFAULT_PORT = 7878
DEFAULT_UNIT = DATA_GIGABYTES
DEFAULT_URLBASE = ""


# Defaults
DEFAULT_SSL = False
DEFAULT_UPCOMING_DAYS = 7
DEFAULT_VERIFY_SSL = False
