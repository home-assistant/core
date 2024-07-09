"""Constants for the Autarco integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Final

DOMAIN: Final = "autarco"
LOGGER = logging.getLogger(__package__)
SCAN_INTERVAL = timedelta(minutes=1)

CONF_PUBLIC_KEY: Final = "public_key"

SENSORS_SOLAR: Final = "solar"
