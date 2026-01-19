"""Constants for Sonarr."""

import logging
from typing import Final

DOMAIN: Final = "sonarr"

# Config Keys
CONF_BASE_PATH = "base_path"
CONF_DAYS = "days"
CONF_INCLUDED = "include_paths"
CONF_UNIT = "unit"
CONF_UPCOMING_DAYS = "upcoming_days"
CONF_WANTED_MAX_ITEMS = "wanted_max_items"

# Defaults
DEFAULT_NAME = "Sonarr"
DEFAULT_UPCOMING_DAYS = 1
DEFAULT_VERIFY_SSL = False
DEFAULT_WANTED_MAX_ITEMS = 50
DEFAULT_MAX_RECORDS: Final = 20

LOGGER = logging.getLogger(__package__)

# Service names
SERVICE_GET_SERIES: Final = "get_series"
SERVICE_GET_EPISODES: Final = "get_episodes"
SERVICE_GET_QUEUE: Final = "get_queue"
SERVICE_GET_DISKSPACE: Final = "get_diskspace"
SERVICE_GET_UPCOMING: Final = "get_upcoming"
SERVICE_GET_WANTED: Final = "get_wanted"

# Service attributes
ATTR_SHOWS: Final = "shows"
ATTR_DISKS: Final = "disks"
ATTR_EPISODES: Final = "episodes"
CONF_ENTRY_ID: Final = "entry_id"
