"""Constants for the Hetzner Cloud integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Final

DOMAIN: Final = "hetzner"
LOGGER = logging.getLogger(__package__)
SCAN_INTERVAL = timedelta(seconds=60)
