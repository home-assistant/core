"""Define constants for the SleepIQ component."""

DOMAIN = "sleepiq"

BED_ID = "bed_id"
IS_IN_BED = "is_in_bed"
SLEEP_NUMBER = "sleep_number"
SENSOR_TYPES = {SLEEP_NUMBER: "SleepNumber", IS_IN_BED: "Is In Bed"}

LEFT = "left"
RIGHT = "right"
SIDE = "side"
SIDES = [LEFT, RIGHT]

SERVICE_SET_SLEEP_NUMBER = "set_sleep_number"
ATTR_ENTITY = "entity_id"
ATTR_SLEEP_NUMBER = "sleep_number"
