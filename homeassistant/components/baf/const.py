"""Constants for the Big Ass Fans integration."""
from enum import IntEnum

DOMAIN = "baf"

QUERY_INTERVAL = 180

RUN_TIMEOUT = 20

PRESET_MODE_AUTO = "Auto"

SPEED_COUNT = 7
SPEED_RANGE = (1, SPEED_COUNT)


class OffOnAuto(IntEnum):
    """Tri-state mode enum that matches the protocol buffer."""

    OFF = 0
    ON = 1
    AUTO = 2
