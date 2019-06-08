"""Constants used by the Sure Petcare component."""
from datetime import timedelta
from enum import IntEnum

DOMAIN = "surepetcare"

DEFAULT_DEVICE_CLASS = "lock"
DEFAULT_ICON = "mdi:cat"

BATTERY_DEFAULT_DEVICE_CLASS = "battery"
BATTERY_DEFAULT_ICON = "mdi:battery"

DEFAULT_SCAN_INTERVAL = timedelta(minutes=3)
DEFAULT_TIMEOUT = 10

CONF_HOUSEHOLD_ID = "household_id"
CONF_FLAPS = "flaps"
CONF_PETS = "pets"

TOPIC_UPDATE = f"{DOMAIN}_data_update"

DATA_SURE_PETCARE = f"data_{DOMAIN}"
DATA_SURE_HOUSEHOLD_NAME = "household_name"
DATA_SURE_LISTENER = "listener"
DATA_SUREPY = "surepy"

SURE_IDS = "sure_ids"

SURE_BATT_VOLTAGE_FULL = 1.6  # voltage
SURE_BATT_VOLTAGE_LOW = 1.25  # voltage
SURE_BATT_VOLTAGE_DIFF = SURE_BATT_VOLTAGE_FULL - SURE_BATT_VOLTAGE_LOW


class SureProductID(IntEnum):
    """Sure Petcare API Product IDs."""

    ROUTER = 1      # Sure Hub
    PET_FLAP = 3    # Pet Door Connect
    CAT_FLAP = 6    # Cat Door Connect


# Thanks to @rcastberg for discovering the IDs used by the Sure Petcare API."""
class SureLocationID(IntEnum):
    """Sure Petcare API Location IDs."""

    INSIDE = 1
    OUTSIDE = 2
    UNKNOWN = -1


class SureLockStateID(IntEnum):
    """Sure Petcare API State IDs."""

    UNLOCKED = 0
    LOCKED_IN = 1
    LOCKED_OUT = 2
    LOCKED_ALL = 3
    CURFEW = 4
    CURFEW_LOCKED = -1
    CURFEW_UNLOCKED = -2
    CURFEW_UNKNOWN = -3


class SureEventID(IntEnum):
    """Sure Petcare API Event IDs."""

    MOVE = 0
    MOVE_UNKNOWN_ANIMAL = 7     # movement of unknown animal
    BATTERY_WARNING = 1
    LOCK_ST = 6
    USR_IFO = 12
    USR_NEW = 17
    CURFEW = 20


class SureThingID(IntEnum):
    """Sure Petcare thing Types."""

    HUB = 0
    FLAP = 1
    PET = 2
