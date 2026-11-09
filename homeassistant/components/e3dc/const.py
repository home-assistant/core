"""Constants for the E3/DC integration."""

from enum import StrEnum

DOMAIN = "e3dc"

DEFAULT_NAME = "E3/DC"
DEFAULT_PORT = 502
# The manual names no unit ID. E3/DC installations answer on 1.
UNIT_ID = 1
# Poll every 5 seconds because the power flows change from second to second
SCAN_INTERVAL = 5


class PartKind(StrEnum):
    """A kind of part with its own device. The value is its device translation key."""

    POWER_METER = "power_meter"
    INVERTER = "inverter"
