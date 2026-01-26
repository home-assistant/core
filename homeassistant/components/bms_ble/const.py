"""Constants for the BLE Battery Management System integration."""

import logging
from typing import Final

DOMAIN: Final[str] = "bms_ble"
LOGGER: Final[logging.Logger] = logging.getLogger(__package__)
UPDATE_INTERVAL: Final[int] = 30  # [s]

# attributes (do not change)

ATTR_BALANCE_CUR: Final[str] = "balance_current"  # [A]
ATTR_BATTERY_HEALTH: Final[str] = "battery_health"  # [%]
ATTR_CELL_COUNT: Final[str] = "cell_count"  # [#]
ATTR_CELL_VOLTAGES: Final[str] = "cell_voltages"  # [V]

ATTR_CURRENT: Final[str] = "current"  # [A]
ATTR_CYCLE_CAP: Final[str] = "cycle_capacity"  # [Wh]
ATTR_CYCLE_CHRG: Final[str] = "cycle_charge"  # [Ah]
ATTR_CYCLES: Final[str] = "cycles"  # [#]
ATTR_DELTA_VOLTAGE: Final[str] = "delta_cell_voltage"  # [V]


ATTR_LQ: Final[str] = "link_quality"  # [%]
ATTR_MAX_VOLTAGE: Final[str] = "max_cell_voltage"  # [V]
ATTR_MIN_VOLTAGE: Final[str] = "min_cell_voltage"  # [V]
ATTR_POWER: Final[str] = "power"  # [W]
ATTR_PROBLEM: Final[str] = "problem"  # [bool]

ATTR_RSSI: Final[str] = "rssi"  # [dBm]
ATTR_RUNTIME: Final[str] = "runtime"  # [s]
ATTR_TEMP_SENSORS: Final[str] = "temperature_sensors"  # [°C]

BINARY_SENSORS: Final[int] = 0  # total number of binary sensors
LINK_SENSORS: Final[int] = 2  # total number of sensors for connection quality
SENSORS: Final[int] = 12  # total number of sensors
