"""Constants for the SolarEdge Modbus integration."""

from datetime import timedelta
import logging
from typing import Final

DOMAIN: Final = "solaredge_modbus"
LOGGER = logging.getLogger(__package__)

CONF_BAUDRATE: Final = "baudrate"
CONF_UNIT_ID: Final = "unit_id"

TYPE_SERIAL: Final = "serial"
TYPE_TCP: Final = "tcp"

# SolarEdge's factory defaults: Modbus TCP on port 1502, RS485 at 115200 baud
# 8N1, device ID 1.
DEFAULT_BAUDRATE: Final = 115200
DEFAULT_PORT: Final = 1502
DEFAULT_UNIT_ID: Final = 1

# Sub-system names as the library reports them in an UpdateReport.
SUBSYSTEM_COMMON: Final = "common"
SUBSYSTEM_INVERTER: Final = "inverter"

# How the library names the blocks it probes for.
SUBSYSTEM_BATTERIES: Final = "batteries"
SUBSYSTEM_METERS: Final = "meters"

# The writable control blocks, as an UpdateReport names them. Export control's
# read spans storage control, so the library reads and reports the two as one.
SUBSYSTEM_ADVANCED_POWER_CONTROL: Final = "advanced_power_control"
SUBSYSTEM_POWER_CONTROL: Final = "power_control"
SUBSYSTEM_SITE_CONTROL: Final = "site_control"

# Local Modbus is cheap to read and PV production moves fast.
SCAN_INTERVAL: Final = timedelta(seconds=10)

# The control blocks hold what the site was told to do; they only move when
# something writes them, so they do not need a live measurement's cadence.
SETTINGS_SCAN_INTERVAL: Final = timedelta(minutes=5)

# Meters and batteries are wired to an inverter by hand, usually with the power
# off, so looking for a change now and then is often enough.
ATTACHMENT_SCAN_INTERVAL: Final = timedelta(minutes=15)
