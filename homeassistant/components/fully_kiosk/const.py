"""Constants for the Fully Kiosk Browser integration."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Final

DOMAIN: Final = "fully_kiosk"

LOGGER = logging.getLogger(__package__)
UPDATE_INTERVAL = timedelta(seconds=30)

DEFAULT_PORT = 2323
