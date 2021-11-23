"""Constants for Radarr."""
from datetime import timedelta
import logging
from homeassistant.const import DATA_GIGABYTES

LOGGER = logging.getLogger(__name__)


DOMAIN = "radarr"

# Config Keys
CONF_BASE_PATH = "base_path"
CONF_UPCOMING_DAYS = "upcoming_days"
CONF_WANTED_MAX_ITEMS = "wanted_max_items"
CONF_DAYS = "days"
CONF_INCLUDED = "include_paths"
CONF_UNIT = "unit"
CONF_URLBASE = "urlbase"

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 7878
DEFAULT_URLBASE = ""
DEFAULT_DAYS = "1"
DEFAULT_UNIT = DATA_GIGABYTES

SCAN_INTERVAL = timedelta(minutes=10)


# Defaults
DEFAULT_BASE_PATH = "/api"
DEFAULT_SSL = False
DEFAULT_UPCOMING_DAYS = 1
DEFAULT_VERIFY_SSL = False
DEFAULT_WANTED_MAX_ITEMS = 50
