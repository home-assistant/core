"""Constants for the BLUETTI Modbus integration."""

from datetime import timedelta
import logging
from typing import Final

DOMAIN: Final = "bluetti_modbus"
LOGGER = logging.getLogger(__package__)

CONF_UNIT_ID: Final = "unit_id"

# BLUETTI's factory default: Modbus TCP on port 502, unit id 1.
DEFAULT_PORT: Final = 502
DEFAULT_UNIT_ID: Final = 1

# The only power-station model bluetti-modbus-lib currently supports over
# Modbus TCP. EP2000 was removed pending confirmation it actually exposes
# Modbus TCP at all - see
# bluetti-official/bluetti-home-assistant#125. "smeter" is a standalone
# accessory, never something a user sets up as its own Modbus device.
DEVICE_TYPE_BALCO260: Final = "balco260"

# This device's Modbus TCP stack is known to become unresponsive under
# polling pressure - proven in production at this interval in the bluetti
# HACS integration's own Modbus coordinator. Do not poll faster.
SCAN_INTERVAL: Final = timedelta(seconds=30)

# Excluded from both the read plan and entity creation - restrict_fields() in
# __init__.py takes this same set, so the coordinator never polls a register
# nothing here reads.
#
# ac_o_switch/g_i_switch/g_o_switch/b_soc_high/b_soc_low belong on other
# platforms once they exist (switch, number/select), not on sensor - creating
# them here now would mean a breaking entity-domain change or a leftover
# duplicate once those follow-up PRs land.
#
# d_inverter_fault/d_inverter_warning: bluetti-modbus 0.1.4's InverterFault
# and InverterWarning enums each define only their zero ("no fault"/"no
# warning") member, so a real, non-zero code has nothing to decode to.
# Excluded until the library represents the actual fault/warning bitmaps,
# rather than shipping a sensor that goes unknown exactly when it would
# matter.
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
