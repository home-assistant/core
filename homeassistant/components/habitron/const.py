"""Constants for the Habitron integration.

Integration-level values only -- the domain, the heartbeat interval and the
sentinel for a hub on Home Assistant's own machine. Everything the bus itself
defines (protocol indices, module codes, event ids, the hub's identity rule)
belongs to ``habitron_client``, which is where a new constant of that kind
goes.
"""

from datetime import timedelta
from typing import Final

DOMAIN = "habitron"
CONF_DEFAULT_HOST = "local"  # default host string of SmartCenter, uses own ip

# Heartbeat interval used by the coordinator. Not user-configurable per
# Home Assistant integration guidelines — each poll is CRC-deduplicated and the
# parser fires per-member listeners only on an actual change, so a fixed
# interval is the right shape.
SCAN_INTERVAL: Final = timedelta(seconds=10)
