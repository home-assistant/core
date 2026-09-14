"""Constants for the BLUETTI Modbus integration."""

from datetime import timedelta
import logging
from typing import Final

DOMAIN: Final = "bluetti_modbus"
LOGGER = logging.getLogger(__package__)

CONF_UNIT_ID: Final = "unit_id"

# BLUETTI's factory defaults.
DEFAULT_PORT: Final = 502
DEFAULT_UNIT_ID: Final = 1

DEVICE_TYPE_BALCO260: Final = "balco260"

# The device's Modbus TCP stack becomes unresponsive when polled faster.
SCAN_INTERVAL: Final = timedelta(seconds=30)

# Left out of the read plan: writable controls that belong on the switch and
# number platforms, and fault/warning enums the library only decodes for
# their zero member so far.
EXCLUDED_FIELDS: Final = frozenset(
    {
        "ac_o_switch",
        "g_i_switch",
        "g_o_switch",
        "b_soc_high",
        "b_soc_low",
        "d_inverter_fault",
        "d_inverter_warning",
    }
)
