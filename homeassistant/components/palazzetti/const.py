"""Constants for the Palazzetti integration."""

from datetime import timedelta
import logging
from typing import Final

from homeassistant.helpers.typing import StateType

DOMAIN: Final = "palazzetti"
PALAZZETTI: Final = "Palazzetti"
LOGGER = logging.getLogger(__package__)
SCAN_INTERVAL = timedelta(seconds=30)
ON_OFF_NOT_AVAILABLE = "on_off_not_available"
ERROR_INVALID_FAN_MODE = "invalid_fan_mode"
ERROR_INVALID_TARGET_TEMPERATURE = "invalid_target_temperature"
ERROR_CANNOT_CONNECT = "cannot_connect"

FAN_SILENT: Final = "silent"
FAN_HIGH: Final = "high"
FAN_AUTO: Final = "auto"
FAN_MODES: Final = [FAN_SILENT, "1", "2", "3", "4", "5", FAN_HIGH, FAN_AUTO]

STATUS_TO_HA: Final[dict[StateType, str]] = {
    0: "off",
    1: "off_timer",
    2: "test_fire",
    3: "heatup",
    4: "fueling",
    5: "ign_test",
    6: "burning",
    7: "burning_mod",
    8: "unknown",
    9: "cool_fluid",
    10: "fire_stop",
    11: "clean_fire",
    12: "cooling",
    50: "cleanup",
    51: "ecomode",
    241: "chimney_alarm",
    243: "grate_error",
    244: "pellet_water_error",
    245: "t05_error",
    247: "hatch_door_open",
    248: "pressure_error",
    249: "main_probe_failure",
    250: "flue_probe_failure",
    252: "exhaust_temp_high",
    253: "pellet_finished",
    501: "off",
    502: "fueling",
    503: "ign_test",
    504: "burning",
    505: "firewood_finished",
    506: "cooling",
    507: "clean_fire",
    1000: "general_error",
    1001: "general_error",
    1239: "door_open",
    1240: "temp_too_high",
    1241: "cleaning_warning",
    1243: "fuel_error",
    1244: "pellet_water_error",
    1245: "t05_error",
    1247: "hatch_door_open",
    1248: "pressure_error",
    1249: "main_probe_failure",
    1250: "flue_probe_failure",
    1252: "exhaust_temp_high",
    1253: "pellet_finished",
    1508: "general_error",
}
