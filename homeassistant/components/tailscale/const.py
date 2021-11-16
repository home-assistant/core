"""Constants for the Tailscale integration."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Final

DOMAIN: Final = "tailscale"

LOGGER = logging.getLogger(__package__)
SCAN_INTERVAL = timedelta(minutes=1)

ENTRY_TYPE_SERVICE: Final = "service"
CONF_TAILNET: Final = "tailnet"
