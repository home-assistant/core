"""Constants for the gridX integration."""

from datetime import timedelta
import logging
from typing import Final

DOMAIN: Final = "gridx"

LOGGER = logging.getLogger(__package__)

# The gridX cloud publishes a new live snapshot roughly once a minute; polling
# faster only produces duplicate values against a third-party service.
LIVE_UPDATE_INTERVAL: Final = timedelta(seconds=60)

# Per-request timeout; the cloud fans out to every system of the account.
HTTP_TIMEOUT: Final = 20
