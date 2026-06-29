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
# Home Assistant integration guidelines — the bus protocol itself is
# CRC-deduplicated and state changes arrive on a separate push channel,
# so a fixed value is the right shape.
SCAN_INTERVAL: Final = timedelta(seconds=10)
RESTART_ALL = 0xFF
HUB_UID = "hub_uid"
ROUTER_NMBR = "rtr_nmbr"
MOD_NMBR = "mod_nmbr"
EVNT_TYPE = "evnt_type"
EVNT_ARG1 = "evnt_arg1"
EVNT_ARG2 = "evnt_arg2"
EVNT_ARG3 = "evnt_arg3"
EVNT_ARG4 = "evnt_arg4"
EVNT_ARG5 = "evnt_arg5"
