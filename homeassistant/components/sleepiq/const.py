"""Define constants for the SleepIQ component."""

DATA_SLEEPIQ = "data_sleepiq"
DOMAIN = "sleepiq"

ACTUATOR = "actuator"
BED = "bed"
FIRMNESS = "firmness"
ICON_EMPTY = "mdi:bed-empty"
ICON_OCCUPIED = "mdi:bed"
IS_IN_BED = "is_in_bed"
PRESSURE = "pressure"
SLEEP_NUMBER = "sleep_number"
ENTITY_TYPES = {
    ACTUATOR: "Position",
    FIRMNESS: "Firmness",
    PRESSURE: "Pressure",
    IS_IN_BED: "Is In Bed",
    SLEEP_NUMBER: "SleepNumber",
}

LEFT = "left"
RIGHT = "right"
SIDES = [LEFT, RIGHT]

SLEEPIQ_DATA = "sleepiq_data"
SLEEPIQ_STATUS_COORDINATOR = "sleepiq_status"
