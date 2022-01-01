"""Define constants for the SleepIQ component."""

from datetime import timedelta

DOMAIN = "sleepiq"
DEFAULT_SCAN_INTERVAL = timedelta(seconds=60)
CONFIG_ENTRY_UPDATE_SIGNAL_TEMPLATE = f"{DOMAIN}_config_entry_update:" "{}"
ICON_EMPTY = "mdi:bed-empty"
ICON_OCCUPIED = "mdi:bed"
NAME = "SleepNumber"

BED = "bed"
FOUNDATION = "foundation"
IS_IN_BED = "is_in_bed"
SLEEP_NUMBER = "sleep_number"
ACTUATOR = "position"
SENSOR_TYPES = {
    SLEEP_NUMBER: "SleepNumber",
    IS_IN_BED: "Is In Bed",
    ACTUATOR: "Position",
}

LEFT = "left"
RIGHT = "right"
SIDES = [LEFT, RIGHT]

HEAD = "head"
FOOT = "foot"
ACTUATORS = [HEAD, FOOT]

ATTRIBUTES = {
    LEFT: {HEAD: "fsLeftHeadPosition", FOOT: "fsLeftFootPosition"},
    RIGHT: {HEAD: "fsRightHeadPosition", FOOT: "fsRightFootPosition"},
}
