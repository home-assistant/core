"""Constants for the Forecast.Solar integration."""
from __future__ import annotations

from typing import Final

from homeassistant.components.sensor import STATE_CLASS_MEASUREMENT
from homeassistant.const import (
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_TIMESTAMP,
    ENERGY_KILO_WATT_HOUR,
    POWER_WATT,
)

from .models import ForecastSolarSensor

DOMAIN = "forecast_solar"

CONF_DECLINATION = "declination"
CONF_AZIMUTH = "azimuth"
CONF_MODULES_POWER = "modules power"
CONF_DAMPING = "damping"
ATTR_ENTRY_TYPE: Final = "entry_type"
ENTRY_TYPE_SERVICE: Final = "service"

SENSORS: list[ForecastSolarSensor] = [
    ForecastSolarSensor(
        key="energy_production_today",
        name="Estimated Energy Production - Today",
        device_class=DEVICE_CLASS_ENERGY,
        unit_of_measurement=ENERGY_KILO_WATT_HOUR,
    ),
    ForecastSolarSensor(
        key="energy_production_tomorrow",
        name="Estimated Energy Production - Tomorrow",
        device_class=DEVICE_CLASS_ENERGY,
        unit_of_measurement=ENERGY_KILO_WATT_HOUR,
    ),
    ForecastSolarSensor(
        key="power_highest_peak_time_today",
        name="Highest Power Peak Time - Today",
        device_class=DEVICE_CLASS_TIMESTAMP,
    ),
    ForecastSolarSensor(
        key="power_highest_peak_time_tomorrow",
        name="Highest Power Peak Time - Tomorrow",
        device_class=DEVICE_CLASS_TIMESTAMP,
    ),
    ForecastSolarSensor(
        key="power_production_now",
        name="Estimated Power Production - Now",
        device_class=DEVICE_CLASS_POWER,
        state_class=STATE_CLASS_MEASUREMENT,
        unit_of_measurement=POWER_WATT,
    ),
    ForecastSolarSensor(
        key="power_production_next_hour",
        name="Estimated Power Production - Next Hour",
        device_class=DEVICE_CLASS_POWER,
        entity_registry_enabled_default=False,
        unit_of_measurement=POWER_WATT,
    ),
    ForecastSolarSensor(
        key="power_production_next_12hours",
        name="Estimated Power Production - Next 12 Hours",
        device_class=DEVICE_CLASS_POWER,
        entity_registry_enabled_default=False,
        unit_of_measurement=POWER_WATT,
    ),
    ForecastSolarSensor(
        key="power_production_next_24hours",
        name="Estimated Power Production - Next 24 Hours",
        device_class=DEVICE_CLASS_POWER,
        entity_registry_enabled_default=False,
        unit_of_measurement=POWER_WATT,
    ),
    ForecastSolarSensor(
        key="energy_current_hour",
        name="Estimated Energy Production - This Hour",
        device_class=DEVICE_CLASS_ENERGY,
        unit_of_measurement=ENERGY_KILO_WATT_HOUR,
    ),
    ForecastSolarSensor(
        key="energy_next_hour",
        name="Estimated Energy Production - Next Hour",
        device_class=DEVICE_CLASS_ENERGY,
        unit_of_measurement=ENERGY_KILO_WATT_HOUR,
    ),
]
