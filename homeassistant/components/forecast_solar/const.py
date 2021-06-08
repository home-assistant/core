"""Constants for the Forecast Solar integration."""
from __future__ import annotations

from typing import Any

from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_NAME,
    ATTR_UNIT_OF_MEASUREMENT,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_TIMESTAMP,
    ENERGY_KILO_WATT_HOUR,
    POWER_WATT,
)

DOMAIN = "forecast_solar"

CONF_DECLINATION = "declination"
CONF_AZIMUTH = "azimuth"
CONF_MODULES_POWER = "modules power"
CONF_DAMPING = "damping"

TEST_DATA = {
    CONF_DECLINATION: 20,
    CONF_AZIMUTH: 10,
    CONF_MODULES_POWER: 1600,
}

TEST_OPTION_DATA = {
    CONF_DECLINATION: 20,
    CONF_AZIMUTH: 10,
    CONF_MODULES_POWER: 1600,
    CONF_DAMPING: 0.5,
}

SENSORS: dict[str, dict[str, Any]] = {
    "energy_production_today": {
        ATTR_NAME: "Estimated Energy Production - Today",
        ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
        ATTR_DEVICE_CLASS: DEVICE_CLASS_ENERGY,
    },
    "energy_production_tomorrow": {
        ATTR_NAME: "Estimated Energy Production - Tomorrow",
        ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
        ATTR_DEVICE_CLASS: DEVICE_CLASS_ENERGY,
    },
    "power_highest_peak_time_today": {
        ATTR_NAME: "Highest Power Peak Time - Today",
        ATTR_UNIT_OF_MEASUREMENT: None,
        ATTR_DEVICE_CLASS: DEVICE_CLASS_TIMESTAMP,
    },
    "power_highest_peak_time_tomorrow": {
        ATTR_NAME: "Highest Power Peak Time - Tomorrow",
        ATTR_UNIT_OF_MEASUREMENT: None,
        ATTR_DEVICE_CLASS: DEVICE_CLASS_TIMESTAMP,
    },
    "power_production_now": {
        ATTR_NAME: "Estimated Power Production - Now",
        ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
        ATTR_DEVICE_CLASS: DEVICE_CLASS_POWER,
    },
    "power_production_next_hour": {
        ATTR_NAME: "Estimated Power Production - Next Hour",
        ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
        ATTR_DEVICE_CLASS: DEVICE_CLASS_POWER,
    },
    "power_production_next_12hours": {
        ATTR_NAME: "Estimated Power Production - Next 12 Hours",
        ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
        ATTR_DEVICE_CLASS: DEVICE_CLASS_POWER,
    },
    "power_production_next_24hours": {
        ATTR_NAME: "Estimated Power Production - Next 24 Hours",
        ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
        ATTR_DEVICE_CLASS: DEVICE_CLASS_POWER,
    },
    "energy_current_hour": {
        ATTR_NAME: "Estimated Energy Production - This Hour",
        ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
        ATTR_DEVICE_CLASS: DEVICE_CLASS_ENERGY,
    },
    "energy_next_hour": {
        ATTR_NAME: "Estimated Energy Production - Next Hour",
        ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
        ATTR_DEVICE_CLASS: DEVICE_CLASS_ENERGY,
    },
}
