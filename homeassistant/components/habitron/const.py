"""Constants for the Habitron integration.

Protocol indices, module codes and event ids now live in the
``habitron_client`` library (the integration is a thin wrapper). Only the
integration-level constants (domain, service keys, heartbeat interval) remain
here.
"""

from datetime import timedelta
from enum import Enum
from typing import Final

DOMAIN = "habitron"  # internal name of the integration, matches the directory
CONF_DEFAULT_HOST = "local"  # default host string of SmartCenter, uses own ip

# Heartbeat interval used by the coordinator. Not user-configurable per
# Home Assistant integration guidelines — the bus protocol itself is
# CRC-deduplicated and state changes arrive on a separate push channel,
# so a fixed value is the right shape.
SCAN_INTERVAL: Final = timedelta(seconds=10)
RESTART_RTR = 0
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
RESTART_KEY_NMBR = "mod_nmbr"
FILE_MOD_NMBR = "mod_nmbr"


class DaytimeMode(Enum):
    """Habitron daytime mode states."""

    day = 1
    night = 2
    undefined = 3


class AlarmMode(Enum):
    """Habitron alarm mode states."""

    off = 0
    on = 4


class GroupMode(Enum):
    """Habitron group mode states."""

    absent = 16
    present = 32
    sleeping = 48
    update = 63
    config = 64
    user1 = 80
    user2 = 96
    vacation = 112
