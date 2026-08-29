"""Constants for the SolarEdge Modbus integration."""

from datetime import timedelta
import logging
from typing import Final

DOMAIN: Final = "solaredge_modbus"
LOGGER = logging.getLogger(__package__)

CONF_UNIT_ID: Final = "unit_id"

# How the inverter is reached is stored from the start, so that an inverter on
# something other than the network needs no migration to say so.
TYPE_TCP: Final = "tcp"

# SolarEdge's factory defaults: Modbus TCP on port 1502, device ID 1.
DEFAULT_PORT: Final = 1502
DEFAULT_UNIT_ID: Final = 1

# Sub-system names as the library reports them in an UpdateReport.
SUBSYSTEM_COMMON: Final = "common"
SUBSYSTEM_INVERTER: Final = "inverter"

# How the library names the meter block it probes for.
SUBSYSTEM_METERS: Final = "meters"

# Local Modbus is cheap to read and PV production moves fast.
SCAN_INTERVAL: Final = timedelta(seconds=10)
