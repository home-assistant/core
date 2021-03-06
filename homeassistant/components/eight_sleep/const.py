"""Constants for Eight Sleep."""
CONF_PARTNER = "partner"
DOMAIN = "eight_sleep"
DEFAULT_PARTNER = False
DATA_EIGHT = "eight_sleep"
SENSORS = [
    "current_sleep",
    "current_sleep_fitness",
    "last_sleep",
    "bed_state",
    "bed_temp",
    "sleep_stage",
    "room_temp",
]

NAME_MAP = {
    "left_current_sleep": "Left Sleep Session",
    "left_current_sleep_fitness": "Left Sleep Fitness",
    "left_last_sleep": "Left Previous Sleep Session",
    "left_bed_state": "Left Bed State",
    "left_presence": "Left Bed Presence",
    "left_bed_temp": "Left Bed Temperature",
    "left_sleep_stage": "Left Sleep Stage",
    "right_current_sleep": "Right Sleep Session",
    "right_current_sleep_fitness": "Right Sleep Fitness",
    "right_last_sleep": "Right Previous Sleep Session",
    "right_bed_state": "Right Bed State",
    "right_presence": "Right Bed Presence",
    "right_bed_temp": "Right Bed Temperature",
    "right_sleep_stage": "Right Sleep Stage",
    "room_temp": "Room Temperature",
}
