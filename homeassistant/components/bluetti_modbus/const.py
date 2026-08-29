"""Constants for the BLUETTI Modbus integration."""

from datetime import timedelta
import logging
from typing import Final

DOMAIN: Final = "bluetti_modbus"
LOGGER = logging.getLogger(__package__)

CONF_UNIT_ID: Final = "unit_id"
CONF_DEVICE_TYPE: Final = "device_type"

# BLUETTI's factory default: Modbus TCP on port 502, unit id 1.
DEFAULT_PORT: Final = 502
DEFAULT_UNIT_ID: Final = 1

# The power-station models bluetti-modbus-lib supports as a top-level product.
# "smeter" is deliberately excluded: it is a standalone accessory attached to
# a power station, never something a user sets up as its own Modbus device.
DEVICE_TYPE_BALCO260: Final = "balco260"
DEVICE_TYPE_EP2000: Final = "ep2000"
DEVICE_TYPES: Final = (DEVICE_TYPE_BALCO260, DEVICE_TYPE_EP2000)

# This device's Modbus TCP stack is known to become unresponsive under
# polling pressure - proven in production at this interval in the bluetti
# HACS integration's own Modbus coordinator. Do not poll faster.
SCAN_INTERVAL: Final = timedelta(seconds=30)

# These belong on other platforms once they exist (switch, number/select), not
# on sensor - creating them here now would mean a breaking entity-domain
# change or a leftover duplicate once those follow-up PRs land. Restricted out
# of the device's read plan entirely (not just entity creation) so the
# coordinator does not keep polling registers no entity here reads.
EXCLUDED_FIELDS: Final = frozenset(
    {"ac_o_switch", "g_i_switch", "g_o_switch", "b_soc_high", "b_soc_low"}
)
