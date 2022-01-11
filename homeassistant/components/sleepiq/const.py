"""Define constants for the SleepIQ component."""

DOMAIN = "sleepiq"

BED = "bed"
CONFIG_ENTRY_UPDATE_SIGNAL_TEMPLATE = f"{DOMAIN}_config_entry_update:" "{}"
ICON_EMPTY = "mdi:bed-empty"
ICON_OCCUPIED = "mdi:bed"
IS_IN_BED = "is_in_bed"
SLEEP_NUMBER = "sleep_number"
SENSOR_TYPES = {SLEEP_NUMBER: "SleepNumber", IS_IN_BED: "Is In Bed"}

LEFT = "left"
RIGHT = "right"
SIDES = [LEFT, RIGHT]
