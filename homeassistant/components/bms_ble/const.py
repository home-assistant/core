"""Constants for the BLE Battery Management System integration."""

import logging
from typing import Final

DOMAIN: Final = "bms_ble"
LOGGER: Final[logging.Logger] = logging.getLogger(__package__)
LOW_RSSI: Final = -75  # dBm considered low signal strength
UPDATE_INTERVAL: Final = 30  # in seconds

ATTR_BALANCE_CUR: Final = "balance_current"
ATTR_BATTERY_HEALTH: Final = "battery_health"
ATTR_CELL_COUNT: Final = "cell_count"
ATTR_CELL_VOLTAGES: Final = "cell_voltages"

ATTR_CURRENT: Final = "current"
ATTR_CYCLE_CAP: Final = "cycle_capacity"
ATTR_CYCLE_CHRG: Final = "cycle_charge"
ATTR_CYCLES: Final = "cycles"
ATTR_DELTA_VOLTAGE: Final = "delta_cell_voltage"


ATTR_LQ: Final = "link_quality"
ATTR_MAX_VOLTAGE: Final = "max_cell_voltage"
ATTR_MIN_VOLTAGE: Final = "min_cell_voltage"
ATTR_POWER: Final = "power"
ATTR_PROBLEM: Final = "problem"

ATTR_RSSI: Final = "rssi"
ATTR_RUNTIME: Final = "runtime"
ATTR_TEMP_SENSORS: Final = "temperature_sensors"

BINARY_SENSORS: Final = 0  # total number of binary sensors
LINK_SENSORS: Final = 2  # total number of sensors for connection quality
SENSORS: Final = 12  # total number of sensors
