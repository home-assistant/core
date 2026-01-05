"""Constants for the PulseGrow integration."""

from __future__ import annotations

import logging
from typing import Final

# Domain matches the brand name "PulseGrow" from Pulse Labs
DOMAIN: Final = "pulsegrow"
MANUFACTURER: Final = "Pulse Labs, Inc."
LOGGER: Final = logging.getLogger(__name__)

# Default polling interval (60 seconds minimum for cloud services)
DEFAULT_SCAN_INTERVAL: Final = 60
