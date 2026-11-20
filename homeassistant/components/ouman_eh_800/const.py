"""Constants for the Ouman EH-800 integration."""

from enum import StrEnum

DOMAIN = "ouman_eh_800"

DEFAULT_SCAN_INTERVAL_SECONDS = 60


class OumanDevice(StrEnum):
    """Logical device that an entity belongs to."""

    MAIN = "main"
    L1 = "l1"
    L2 = "l2"
