"""Constants for the Palazzetti integration."""

from datetime import timedelta
import logging
from typing import Final

DOMAIN: Final = "palazzetti"
PALAZZETTI: Final = "Palazzetti"
LOGGER = logging.getLogger(__package__)
SCAN_INTERVAL = timedelta(seconds=5)
ACTION_NOT_UNAVAILABLE = "action_not_available"
C = "action_not_available"

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
AVAILABLE: Final = "available"
TARGET_TEMPERATURE: Final = "target_temperature"
ROOM_TEMPERATURE: Final = "room_temperature"
OUTLET_TEMPERATURE: Final = "outlet_temperature"
EXHAUST_TEMPERATURE: Final = "exhaust_temperature"
PELLET_QUANTITY: Final = "pellet_quantity"
FAN_SPEED: Final = "fan_speed"
IS_HEATING: Final = "is_heating"

FAN_SILENT: Final = "SILENT"
FAN_HIGH: Final = "HIGH"
FAN_AUTO: Final = "AUTO"
FAN_MODES: Final = [FAN_SILENT, "1", "2", "3", "4", "5", FAN_HIGH, FAN_AUTO]
