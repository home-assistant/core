"""Constants for the Palazzetti integration."""

from datetime import timedelta
import logging
from typing import Final

DOMAIN: Final = "palazzetti"
PALAZZETTI: Final = "Palazzetti"
LOGGER = logging.getLogger(__package__)
SCAN_INTERVAL = timedelta(seconds=5)
ACTION_NOT_UNAVAILABLE = "action_not_available"

API_NAME: Final = "LABEL"
API_HOST: Final = "IP"
API_MAC: Final = "MAC"
API_TARGET_TEMPERATURE: Final = "SETP"
API_ROOM_TEMPERATURE: Final = "T1"
API_OUTPUT_TEMPERATURE: Final = "T2"
API_EXHAUST_TEMPERATURE: Final = "T3"
API_PELLET_QUANTITY: Final = "PQT"
API_FAN_MODE: Final = "F2L"
API_MODE: Final = "LSTATUS"
API_HW_VERSION: Final = "SYSTEM"
API_SW_VERSION: Final = "plzbridge"

HUB: Final = "hub"
NAME: Final = "name"
HOST: Final = "host"
MAC: Final = "mac"
TARGET_TEMPERATURE: Final = "target_temperature"
ROOM_TEMPERATURE: Final = "room_temperature"
OUTPUT_TEMPERATURE: Final = "output_temperature"
EXHAUST_TEMPERATURE: Final = "exhaust_temperature"
PELLET_QUANTITY: Final = "pellet_quantity"
FAN_MODE: Final = "fan_mode"
MODE: Final = "mode"

STATUSES: Final = {
    0: "OFF",
    1: "OFF_TIMER",
    2: "TESTFIRE",
    3: "HEATUP",
    4: "FUELING",
    5: "IGNTEST",
    6: "BURNING",
    7: "BURNINGMOD",
    8: "UNKNOWN",
    9: "COOLFLUID",
    10: "FIRESTOP",
    11: "CLEANFIRE",
    12: "COOL",
    50: "CLEANUP",
    51: "ECOMODE",
    241: "CHIMNEY_ALARM",
    243: "GRATE_ERROR",
    244: "PELLET_WATER_ERROR",
    245: "T05_ERROR",
    247: "HATCH_DOOR_OPEN",
    248: "PRESSURE_ERROR",
    249: "MAIN_PROBE_FAILURE",
    250: "FLUE_PROBE_FAILURE",
    252: "EXHAUST_TEMP_HIGH",
    253: "PELLET_FINISHED",
    501: "OFF",
    502: "FUELING",
    503: "IGNTEST",
    504: "BURNING",
    505: "FIREWOOD_FINISHED",
    506: "COOLING",
    507: "CLEANFIRE",
    1000: "GENERAL_ERROR",
    1001: "GENERAL_ERROR",
    1239: "DOOR_OPEN",
    1240: "TEMP_TOO_HIGH",
    1241: "CLEANING_WARNING",
    1243: "FUEL_ERROR",
    1244: "PELLET_WATER_ERROR",
    1245: "T05_ERROR",
    1247: "HATCH_DOOR_OPEN",
    1248: "PRESSURE_ERROR",
    1249: "MAIN_PROBE_FAILURE",
    1250: "FLUE_PROBE_FAILURE",
    1252: "EXHAUST_TEMP_HIGH",
    1253: "PELLET_FINISHED",
    1508: "GENERAL_ERROR",
}

HEATING_STATUSES = [2, 3, 4, 5, 6, 7, 51, 502, 503, 504]

FAN_SILENT: Final = "SILENT"
FAN_HIGH: Final = "HIGH"
FAN_AUTO: Final = "AUTO"
FAN_MODES: Final = [FAN_SILENT, "1", "2", "3", "4", "5", FAN_HIGH, FAN_AUTO]
