"""Constants for the Trovis 557x integration."""

from datetime import timedelta
from typing import Final

DOMAIN: Final = "trovis557x"

CONF_CONNECTION: Final = "connection_entry_id"
CONF_UNIT_ID: Final = "unit_id"

DEFAULT_UNIT_ID: Final = 246  # the controller's default Modbus station address

# A heating controller changes slowly, but we poll aggressively and fixed.
SCAN_INTERVAL: Final = timedelta(seconds=30)
