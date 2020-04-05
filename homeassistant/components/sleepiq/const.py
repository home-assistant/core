"""Define constants for the SleepIQ component."""
from datetime import timedelta

DOMAIN = "sleepiq"

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=30)

IS_IN_BED = "is_in_bed"
SLEEP_NUMBER = "sleep_number"
SENSOR_TYPES = {SLEEP_NUMBER: "SleepNumber", IS_IN_BED: "Is In Bed"}

LEFT = "left"
RIGHT = "right"
SIDES = [LEFT, RIGHT]
