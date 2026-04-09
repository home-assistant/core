"""Constants for the Fluss+ integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Final

DOMAIN: Final = "fluss"
LOGGER = logging.getLogger(__name__)
UPDATE_INTERVAL = 60  # seconds
UPDATE_INTERVAL_TIMEDELTA = timedelta(seconds=UPDATE_INTERVAL)

CONF_ICON_TYPE: Final = "icon_type"
DEFAULT_ICON_TYPE: Final = "garage"

ICON_TYPE_MAP: Final[dict[str, str]] = {
    "garage": "mdi:garage",
    "gate": "mdi:gate",
    "door": "mdi:door",
    "boom_gate": "mdi:boom-gate",
    "barrier": "mdi:barrier",
}
