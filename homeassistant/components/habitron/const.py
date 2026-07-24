"""Constants for the Habitron integration.

Protocol indices, module codes and event ids now live in the
``habitron_client`` library (the integration is a thin wrapper). Only the
integration-level constants (domain, service keys, heartbeat interval) remain
here.
"""

from datetime import timedelta
from typing import Final

DOMAIN = "habitron"  # internal name of the integration, matches the directory
CONF_DEFAULT_HOST = "local"  # default host string of SmartCenter, uses own ip

# Heartbeat interval used by the coordinator. Not user-configurable per
# Home Assistant integration guidelines — each poll is CRC-deduplicated and the
# parser fires per-member listeners only on an actual change, so a fixed
# interval is the right shape.
SCAN_INTERVAL: Final = timedelta(seconds=10)
RESTART_ALL = 0xFF
