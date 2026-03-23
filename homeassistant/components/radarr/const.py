"""Constants for Radarr."""

import logging
from typing import Final

DOMAIN: Final = "radarr"

# Config keys
CONF_UPCOMING_DAYS = "upcoming_days"

# Defaults
DEFAULT_NAME = "Radarr"
DEFAULT_URL = "http://127.0.0.1:7878"
DEFAULT_UPCOMING_DAYS = 45

HEALTH_ISSUES = (
    "DownloadClientCheck",
    "DownloadClientStatusCheck",
    "IndexerRssCheck",
    "IndexerSearchCheck",
)

LOGGER = logging.getLogger(__package__)
