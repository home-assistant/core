"""Constants for the Forecast.Solar integration."""
from __future__ import annotations

from datetime import timedelta

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import ENERGY_KILO_WATT_HOUR, POWER_WATT

from .models import ForecastSolarSensorEntityDescription

DOMAIN = "forecast_solar"

CONF_DECLINATION = "declination"
CONF_AZIMUTH = "azimuth"
CONF_MODULES_POWER = "modules power"
CONF_DAMPING = "damping"
CONF_INVERTER_SIZE = "inverter_size"

SENSORS: tuple[ForecastSolarSensorEntityDescription, ...] = (
    ForecastSolarSensorEntityDescription(
        key="energy_production_today",
        name="Estimated energy production - today",
        state=lambda estimate: estimate.energy_production_today / 1000,
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
    ),
    ForecastSolarSensorEntityDescription(
        key="energy_production_tomorrow",
        name="Estimated energy production - tomorrow",
        state=lambda estimate: estimate.energy_production_tomorrow / 1000,
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
    ),
    ForecastSolarSensorEntityDescription(
        key="power_highest_peak_time_today",
        name="Highest power peak time - today",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    ForecastSolarSensorEntityDescription(
        key="power_highest_peak_time_tomorrow",
        name="Highest power peak time - tomorrow",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    ForecastSolarSensorEntityDescription(
        key="power_production_now",
        name="Estimated power production - now",
        device_class=SensorDeviceClass.POWER,
        state=lambda estimate: estimate.power_production_now,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=POWER_WATT,
    ),
    ForecastSolarSensorEntityDescription(
        key="power_production_next_hour",
        state=lambda estimate: estimate.power_production_at_time(
            estimate.now() + timedelta(hours=1)
        ),
        name="Estimated power production - next hour",
        device_class=SensorDeviceClass.POWER,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=POWER_WATT,
    ),
    ForecastSolarSensorEntityDescription(
        key="power_production_next_12hours",
        state=lambda estimate: estimate.power_production_at_time(
            estimate.now() + timedelta(hours=12)
        ),
        name="Estimated power production - next 12 hours",
        device_class=SensorDeviceClass.POWER,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=POWER_WATT,
    ),
    ForecastSolarSensorEntityDescription(
        key="power_production_next_24hours",
        state=lambda estimate: estimate.power_production_at_time(
            estimate.now() + timedelta(hours=24)
        ),
        name="Estimated power production - next 24 hours",
        device_class=SensorDeviceClass.POWER,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=POWER_WATT,
    ),
    ForecastSolarSensorEntityDescription(
        key="energy_current_hour",
        name="Estimated energy production - this hour",
        state=lambda estimate: estimate.energy_current_hour / 1000,
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
    ),
    ForecastSolarSensorEntityDescription(
        key="energy_next_hour",
        state=lambda estimate: estimate.sum_energy_production(1) / 1000,
        name="Estimated energy production - next hour",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
    ),
)
