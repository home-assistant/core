"""Define constants for the SleepIQ component."""

from datetime import timedelta

from sleepyq import FAVORITE, FLAT, READ, SNORE, WATCH_TV, ZERO_G

DOMAIN = "sleepiq"
DEFAULT_SCAN_INTERVAL = timedelta(seconds=60)
CONFIG_ENTRY_UPDATE_SIGNAL_TEMPLATE = f"{DOMAIN}_config_entry_update:" "{}"
ICON_EMPTY = "mdi:bed-empty"
ICON_OCCUPIED = "mdi:bed"
NAME = "SleepNumber"

ACTUATOR = "position"
BED = "bed"
FOUNDATION = "foundation"
IS_IN_BED = "is_in_bed"
PRESET = "preset"
SLEEP_NUMBER = "sleep_number"

SENSOR_TYPES = {
    SLEEP_NUMBER: "SleepNumber",
    IS_IN_BED: "Is In Bed",
    ACTUATOR: "Position",
    PRESET: "Preset",
}

LEFT = "left"
RIGHT = "right"
SIDES = [LEFT, RIGHT]

HEAD = "head"
FOOT = "foot"
ACTUATORS = [HEAD, FOOT]

ATTRIBUTES = {
    LEFT: {
        HEAD: "fsLeftHeadPosition",
        FOOT: "fsLeftFootPosition",
        PRESET: "fsCurrentPositionPresetLeft",
    },
    RIGHT: {
        HEAD: "fsRightHeadPosition",
        FOOT: "fsRightFootPosition",
        PRESET: "fsCurrentPositionPresetRight",
    },
}

NOT_AT_PRESET = "Not at preset"
PRESETS = {
    "Favorite": FAVORITE,
    "Flat": FLAT,
    NOT_AT_PRESET: -1,
    "Read": READ,
    "Snore": SNORE,
    "Watch TV": WATCH_TV,
    "Zero G": ZERO_G,
}
