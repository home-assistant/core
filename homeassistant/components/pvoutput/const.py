"""Constants for the PVOutput integration."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "pvoutput"
PLATFORMS = [Platform.SENSOR]

LOGGER = logging.getLogger(__package__)
SCAN_INTERVAL = timedelta(minutes=2)


CONF_SYSTEM_ID = "system_id"
