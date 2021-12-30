"""Constants for the Nissan Leaf integration."""
from __future__ import annotations

import logging
from typing import Final, Literal

DOMAIN: Final = "nissan_leaf"

LOGGER = logging.getLogger(__package__)

DATA_LEAF = "nissan_leaf_data"

DATA_BATTERY = "battery"
DATA_CHARGING = "charging"
DATA_PLUGGED_IN = "plugged_in"
DATA_CLIMATE = "climate"
DATA_RANGE_AC = "range_ac_on"
DATA_RANGE_AC_OFF = "range_ac_off"

CONF_INTERVAL = "update_interval"
CONF_CHARGING_INTERVAL = "update_interval_charging"
CONF_CLIMATE_INTERVAL = "update_interval_climate"
CONF_VALID_REGIONS = Literal["NNA", "NE", "NCI", "NMA", "NML"]
CONF_FORCE_MILES = "force_miles"

RESTRICTED_BATTERY = 2

MAX_RESPONSE_ATTEMPTS = 3

PYCARWINGS2_SLEEP = 30
