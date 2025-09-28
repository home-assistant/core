"""Define constants for the SleepIQ component."""

DATA_SLEEPIQ = "data_sleepiq"
DOMAIN = "sleepiq"

ACTUATOR = "actuator"
CORE_CLIMATE_TIMER = "core_climate_timer"
CORE_CLIMATE = "core_climate"
BED = "bed"
FIRMNESS = "firmness"
ICON_EMPTY = "mdi:bed-empty"
ICON_OCCUPIED = "mdi:bed"
IS_IN_BED = "is_in_bed"
PRESSURE = "pressure"
SLEEP_NUMBER = "sleep_number"
FOOT_WARMING_TIMER = "foot_warming_timer"
FOOT_WARMER = "foot_warmer"
ENTITY_TYPES = {
    ACTUATOR: "Position",
    CORE_CLIMATE_TIMER: "Core Climate Timer",
    CORE_CLIMATE: "Core Climate",
    FIRMNESS: "Firmness",
    PRESSURE: "Pressure",
    IS_IN_BED: "Is In Bed",
    SLEEP_NUMBER: "SleepNumber",
    FOOT_WARMING_TIMER: "Foot Warming Timer",
    FOOT_WARMER: "Foot Warmer",
}

LEFT = "left"
RIGHT = "right"
SIDES = [LEFT, RIGHT]

SLEEPIQ_DATA = "sleepiq_data"
SLEEPIQ_STATUS_COORDINATOR = "sleepiq_status"
