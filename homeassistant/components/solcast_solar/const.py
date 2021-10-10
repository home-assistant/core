"""Constants for the Solcast Solar integration."""
from __future__ import annotations

from typing import Final

DOMAIN = "solcast_solar"

CONF_APIKEY = "apikey"
CONF_ROOFTOP = "rooftop"
CONF_POLL_INTERVAL = "pollapi_interval"
ATTR_ENTRY_TYPE: Final = "entry_type"
ENTRY_TYPE_SERVICE: Final = "service"

DATA_COORDINATOR = "coordinator"
SERVICE_SOLCAST = "solcastservice"
ATTRIBUTION: Final = "Data retrieved from Solcast"
