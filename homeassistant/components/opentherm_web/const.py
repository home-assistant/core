"""Constants for the OpenTherm Web integration."""
from __future__ import annotations

from datetime import timedelta
import logging

DOMAIN = "opentherm_web"
LOGGER = logging.getLogger(__package__)
SCAN_INTERVAL = timedelta(seconds=5)
HOST = "host"
SECRET = "password"
