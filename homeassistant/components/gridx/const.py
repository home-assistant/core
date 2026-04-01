"""Constants for the GridX integration."""

from datetime import timedelta
import logging
from typing import Final

DOMAIN: Final = "gridx"

LOGGER = logging.getLogger(__package__)

CONF_OEM: Final = "oem"

# Maps OEM key (stored in config entry) -> display label shown in UI.
# Viessmann is intentionally excluded: the realm was shut down end of 2025.
SUPPORTED_OEMS: Final[dict[str, str]] = {
    "eon-home": "EON Home",
}

LIVE_UPDATE_INTERVAL = timedelta(seconds=30)
HIST_UPDATE_INTERVAL = timedelta(hours=1)
