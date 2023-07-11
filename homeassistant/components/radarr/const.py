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
