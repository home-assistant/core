"""Constants for the Nissan Leaf integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "nissan_leaf"

DATA_LEAF: Final = "nissan_leaf_data"

DATA_BATTERY: Final = "battery"
DATA_CHARGING: Final = "charging"
DATA_PLUGGED_IN: Final = "plugged_in"
DATA_CLIMATE: Final = "climate"
DATA_RANGE_AC: Final = "range_ac_on"
DATA_RANGE_AC_OFF: Final = "range_ac_off"

CONF_INTERVAL: Final = "update_interval"
CONF_CHARGING_INTERVAL: Final = "update_interval_charging"
CONF_CLIMATE_INTERVAL: Final = "update_interval_climate"
CONF_FORCE_MILES: Final = "force_miles"

CONF_VALID_REGIONS: Final = ["NNA", "NE", "NCI", "NMA", "NML"]

INITIAL_UPDATE: Final = timedelta(seconds=15)
MIN_UPDATE_INTERVAL: Final = timedelta(minutes=2)
DEFAULT_INTERVAL: Final = timedelta(hours=1)
DEFAULT_CHARGING_INTERVAL: Final = timedelta(minutes=15)
DEFAULT_CLIMATE_INTERVAL: Final = timedelta(minutes=5)
RESTRICTED_INTERVAL: Final = timedelta(hours=12)
RESTRICTED_BATTERY: Final = 2

MAX_RESPONSE_ATTEMPTS: Final = 3

PYCARWINGS2_SLEEP: Final = 40

SIGNAL_UPDATE_LEAF = "nissan_leaf_update"
