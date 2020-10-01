"""Define constants for the SleepIQ component."""

DOMAIN = "sleepiq"

IS_IN_BED = "is_in_bed"
SLEEP_NUMBER = "sleep_number"
SENSOR_TYPES = {SLEEP_NUMBER: "SleepNumber", IS_IN_BED: "Is In Bed"}

LEFT = "left"
RIGHT = "right"
SIDE = "side"
SIDES = [LEFT, RIGHT]
BED = "bed"

PRESET_FAVORITE = 0

SERVICE_SET_SLEEP_NUMBER = "set_sleep_number"
SERVICE_SET_FAVORITE = "set_to_favorite_sleep_number"
