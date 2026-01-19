"""Constants for Radarr."""

import logging
from typing import Final

DOMAIN: Final = "radarr"

# Defaults
DEFAULT_NAME = "Radarr"
DEFAULT_URL = "http://127.0.0.1:7878"

HEALTH_ISSUES = (
    "DownloadClientCheck",
    "DownloadClientStatusCheck",
    "IndexerRssCheck",
    "IndexerSearchCheck",
)

LOGGER = logging.getLogger(__package__)

# Service names
SERVICE_GET_MOVIES: Final = "get_movies"
SERVICE_GET_QUEUE: Final = "get_queue"

# Service attributes
ATTR_MOVIES: Final = "movies"
CONF_ENTRY_ID: Final = "entry_id"
