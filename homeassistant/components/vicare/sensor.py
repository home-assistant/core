"""Viessmann ViCare sensor device."""
from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
import logging

from PyViCare.PyViCare import PyViCareNotSupportedFeatureError, PyViCareRateLimitError
import requests

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.const import (
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_TEMPERATURE,
    ENERGY_KILO_WATT_HOUR,
    PERCENTAGE,
    POWER_WATT,
    TEMP_CELSIUS,
    TIME_HOURS,
)

from . import (
    DOMAIN as VICARE_DOMAIN,
    VICARE_API,
    VICARE_HEATING_TYPE,
    VICARE_NAME,
    HeatingType,
    ViCareRequiredKeysMixin,
)

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPE_TEMPERATURE = "temperature"

SENSOR_OUTSIDE_TEMPERATURE = "outside_temperature"
SENSOR_SUPPLY_TEMPERATURE = "supply_temperature"
SENSOR_RETURN_TEMPERATURE = "return_temperature"

# gas sensors
SENSOR_BOILER_TEMPERATURE = "boiler_temperature"
SENSOR_BURNER_MODULATION = "burner_modulation"
SENSOR_BURNER_STARTS = "burner_starts"
SENSOR_BURNER_HOURS = "burner_hours"
SENSOR_BURNER_POWER = "burner_power"
SENSOR_DHW_GAS_CONSUMPTION_TODAY = "hotwater_gas_consumption_today"
SENSOR_DHW_GAS_CONSUMPTION_THIS_WEEK = "hotwater_gas_consumption_heating_this_week"
SENSOR_DHW_GAS_CONSUMPTION_THIS_MONTH = "hotwater_gas_consumption_heating_this_month"
SENSOR_DHW_GAS_CONSUMPTION_THIS_YEAR = "hotwater_gas_consumption_heating_this_year"
SENSOR_GAS_CONSUMPTION_TODAY = "gas_consumption_heating_today"
SENSOR_GAS_CONSUMPTION_THIS_WEEK = "gas_consumption_heating_this_week"
SENSOR_GAS_CONSUMPTION_THIS_MONTH = "gas_consumption_heating_this_month"
SENSOR_GAS_CONSUMPTION_THIS_YEAR = "gas_consumption_heating_this_year"

# heatpump sensors
SENSOR_COMPRESSOR_STARTS = "compressor_starts"
SENSOR_COMPRESSOR_HOURS = "compressor_hours"
SENSOR_COMPRESSOR_HOURS_LOADCLASS1 = "compressor_hours_loadclass1"
SENSOR_COMPRESSOR_HOURS_LOADCLASS2 = "compressor_hours_loadclass2"
SENSOR_COMPRESSOR_HOURS_LOADCLASS3 = "compressor_hours_loadclass3"
SENSOR_COMPRESSOR_HOURS_LOADCLASS4 = "compressor_hours_loadclass4"
SENSOR_COMPRESSOR_HOURS_LOADCLASS5 = "compressor_hours_loadclass5"

# fuelcell sensors
SENSOR_POWER_PRODUCTION_CURRENT = "power_production_current"
SENSOR_POWER_PRODUCTION_TODAY = "power_production_today"
SENSOR_POWER_PRODUCTION_THIS_WEEK = "power_production_this_week"
SENSOR_POWER_PRODUCTION_THIS_MONTH = "power_production_this_month"
SENSOR_POWER_PRODUCTION_THIS_YEAR = "power_production_this_year"


@dataclass
class ViCareSensorEntityDescription(SensorEntityDescription, ViCareRequiredKeysMixin):
    """Describes ViCare sensor entity."""


SENSOR_TYPES: tuple[ViCareSensorEntityDescription, ...] = (
    ViCareSensorEntityDescription(
        key=SENSOR_OUTSIDE_TEMPERATURE,
        name="Outside Temperature",
        icon=None,
        native_unit_of_measurement=TEMP_CELSIUS,
        value_getter=lambda api: api.getOutsideTemperature(),
        device_class=DEVICE_CLASS_TEMPERATURE,
    ),
    ViCareSensorEntityDescription(
        key=SENSOR_SUPPLY_TEMPERATURE,
        name="Supply Temperature",
        icon=None,
        native_unit_of_measurement=TEMP_CELSIUS,
        value_getter=lambda api: api.getSupplyTemperature(),
        device_class=DEVICE_CLASS_TEMPERATURE,
    ),
    # gas sensors
    ViCareSensorEntityDescription(
        key=SENSOR_BOILER_TEMPERATURE,
        name="Boiler Temperature",
        icon=None,
        native_unit_of_measurement=TEMP_CELSIUS,
        value_getter=lambda api: api.getBoilerTemperature(),
        device_class=DEVICE_CLASS_TEMPERATURE,
    ),
    ViCareSensorEntityDescription(
        key=SENSOR_BURNER_MODULATION,
        name="Burner modulation",
        icon="mdi:percent",
        native_unit_of_measurement=PERCENTAGE,
        value_getter=lambda api: api.getBurnerModulation(),
        device_class=None,
    ),
    ViCareSensorEntityDescription(
        key=SENSOR_DHW_GAS_CONSUMPTION_TODAY,
        name="Hot water gas consumption today",
        icon="mdi:power",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        value_getter=lambda api: api.getGasConsumptionDomesticHotWaterToday(),
        device_class=None,
    ),
    ViCareSensorEntityDescription(
        key=SENSOR_DHW_GAS_CONSUMPTION_THIS_WEEK,
        name="Hot water gas consumption this week",
        icon="mdi:power",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        value_getter=lambda api: api.getGasConsumptionDomesticHotWaterThisWeek(),
        device_class=None,
    ),
    ViCareSensorEntityDescription(
        key=SENSOR_DHW_GAS_CONSUMPTION_THIS_MONTH,
        name="Hot water gas consumption this month",
        icon="mdi:power",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        value_getter=lambda api: api.getGasConsumptionDomesticHotWaterThisMonth(),
        device_class=None,
    ),
    ViCareSensorEntityDescription(
        key=SENSOR_DHW_GAS_CONSUMPTION_THIS_YEAR,
        name="Hot water gas consumption this year",
        icon="mdi:power",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        value_getter=lambda api: api.getGasConsumptionDomesticHotWaterThisYear(),
        device_class=None,
    ),
    ViCareSensorEntityDescription(
        key=SENSOR_GAS_CONSUMPTION_TODAY,
        name="Heating gas consumption today",
        icon="mdi:power",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        value_getter=lambda api: api.getGasConsumptionHeatingToday(),
        device_class=None,
    ),
    ViCareSensorEntityDescription(
        key=SENSOR_GAS_CONSUMPTION_THIS_WEEK,
        name="Heating gas consumption this week",
        icon="mdi:power",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        value_getter=lambda api: api.getGasConsumptionHeatingThisWeek(),
        device_class=None,
    ),
    ViCareSensorEntityDescription(
        key=SENSOR_GAS_CONSUMPTION_THIS_MONTH,
        name="Heating gas consumption this month",
        icon="mdi:power",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        value_getter=lambda api: api.getGasConsumptionHeatingThisMonth(),
        device_class=None,
    ),
    ViCareSensorEntityDescription(
        key=SENSOR_GAS_CONSUMPTION_THIS_YEAR,
        name="Heating gas consumption this year",
        icon="mdi:power",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        value_getter=lambda api: api.getGasConsumptionHeatingThisYear(),
        device_class=None,
    ),
    ViCareSensorEntityDescription(
        key=SENSOR_BURNER_STARTS,
        name="Burner Starts",
        icon="mdi:counter",
        native_unit_of_measurement=None,
        value_getter=lambda api: api.getBurnerStarts(),
        device_class=None,
    ),
    ViCareSensorEntityDescription(
        key=SENSOR_BURNER_HOURS,
        name="Burner Hours",
        icon="mdi:counter",
        native_unit_of_measurement=TIME_HOURS,
        value_getter=lambda api: api.getBurnerHours(),
        device_class=None,
    ),
    # heatpump sensors
    ViCareSensorEntityDescription(
        key=SENSOR_COMPRESSOR_STARTS,
        name="Compressor Starts",
        icon="mdi:counter",
        native_unit_of_measurement=None,
        value_getter=lambda api: api.getCompressorStarts(),
        device_class=None,
    ),
    ViCareSensorEntityDescription(
        key=SENSOR_COMPRESSOR_HOURS,
        name="Compressor Hours",
        icon="mdi:counter",
        native_unit_of_measurement=TIME_HOURS,
        value_getter=lambda api: api.getCompressorHours(),
        device_class=None,
    ),
    ViCareSensorEntityDescription(
        key=SENSOR_COMPRESSOR_HOURS_LOADCLASS1,
        name="Compressor Hours Load Class 1",
        icon="mdi:counter",
        native_unit_of_measurement=TIME_HOURS,
        value_getter=lambda api: api.getCompressorHoursLoadClass1(),
        device_class=None,
    ),
    ViCareSensorEntityDescription(
        key=SENSOR_COMPRESSOR_HOURS_LOADCLASS2,
        name="Compressor Hours Load Class 2",
        icon="mdi:counter",
        native_unit_of_measurement=TIME_HOURS,
        value_getter=lambda api: api.getCompressorHoursLoadClass2(),
        device_class=None,
    ),
    ViCareSensorEntityDescription(
        key=SENSOR_COMPRESSOR_HOURS_LOADCLASS3,
        name="Compressor Hours Load Class 3",
        icon="mdi:counter",
        native_unit_of_measurement=TIME_HOURS,
        value_getter=lambda api: api.getCompressorHoursLoadClass3(),
        device_class=None,
    ),
    ViCareSensorEntityDescription(
        key=SENSOR_COMPRESSOR_HOURS_LOADCLASS4,
        name="Compressor Hours Load Class 4",
        icon="mdi:counter",
        native_unit_of_measurement=TIME_HOURS,
        value_getter=lambda api: api.getCompressorHoursLoadClass4(),
        device_class=None,
    ),
    ViCareSensorEntityDescription(
        key=SENSOR_COMPRESSOR_HOURS_LOADCLASS5,
        name="Compressor Hours Load Class 5",
        icon="mdi:counter",
        native_unit_of_measurement=TIME_HOURS,
        value_getter=lambda api: api.getCompressorHoursLoadClass5(),
        device_class=None,
    ),
    ViCareSensorEntityDescription(
        key=SENSOR_RETURN_TEMPERATURE,
        name="Return Temperature",
        icon=None,
        native_unit_of_measurement=TEMP_CELSIUS,
        value_getter=lambda api: api.getReturnTemperature(),
        device_class=DEVICE_CLASS_TEMPERATURE,
    ),
    # fuelcell sensors
    ViCareSensorEntityDescription(
        key=SENSOR_POWER_PRODUCTION_CURRENT,
        name="Power production current",
        icon=None,
        native_unit_of_measurement=POWER_WATT,
        value_getter=lambda api: api.getPowerProductionCurrent(),
        device_class=DEVICE_CLASS_POWER,
    ),
    ViCareSensorEntityDescription(
        key=SENSOR_POWER_PRODUCTION_TODAY,
        name="Power production today",
        icon=None,
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        value_getter=lambda api: api.getPowerProductionToday(),
        device_class=DEVICE_CLASS_ENERGY,
    ),
    ViCareSensorEntityDescription(
        key=SENSOR_POWER_PRODUCTION_THIS_WEEK,
        name="Power production this week",
        icon=None,
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        value_getter=lambda api: api.getPowerProductionThisWeek(),
        device_class=DEVICE_CLASS_ENERGY,
    ),
    ViCareSensorEntityDescription(
        key=SENSOR_POWER_PRODUCTION_THIS_MONTH,
        name="Power production this month",
        icon=None,
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        value_getter=lambda api: api.getPowerProductionThisMonth(),
        device_class=DEVICE_CLASS_ENERGY,
    ),
    ViCareSensorEntityDescription(
        key=SENSOR_POWER_PRODUCTION_THIS_YEAR,
        name="Power production this year",
        icon=None,
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        value_getter=lambda api: api.getPowerProductionThisYear(),
        device_class=DEVICE_CLASS_ENERGY,
    ),
)

SENSORS_GENERIC = [SENSOR_OUTSIDE_TEMPERATURE, SENSOR_SUPPLY_TEMPERATURE]

SENSORS_BY_HEATINGTYPE = {
    HeatingType.gas: [
        SENSOR_BOILER_TEMPERATURE,
        SENSOR_BURNER_HOURS,
        SENSOR_BURNER_MODULATION,
        SENSOR_BURNER_STARTS,
        SENSOR_DHW_GAS_CONSUMPTION_TODAY,
        SENSOR_DHW_GAS_CONSUMPTION_THIS_WEEK,
        SENSOR_DHW_GAS_CONSUMPTION_THIS_MONTH,
        SENSOR_DHW_GAS_CONSUMPTION_THIS_YEAR,
        SENSOR_GAS_CONSUMPTION_TODAY,
        SENSOR_GAS_CONSUMPTION_THIS_WEEK,
        SENSOR_GAS_CONSUMPTION_THIS_MONTH,
        SENSOR_GAS_CONSUMPTION_THIS_YEAR,
    ],
    HeatingType.heatpump: [
        SENSOR_COMPRESSOR_STARTS,
        SENSOR_COMPRESSOR_HOURS,
        SENSOR_COMPRESSOR_HOURS_LOADCLASS1,
        SENSOR_COMPRESSOR_HOURS_LOADCLASS2,
        SENSOR_COMPRESSOR_HOURS_LOADCLASS3,
        SENSOR_COMPRESSOR_HOURS_LOADCLASS4,
        SENSOR_COMPRESSOR_HOURS_LOADCLASS5,
        SENSOR_RETURN_TEMPERATURE,
    ],
    HeatingType.fuelcell: [
        # gas
        SENSOR_BOILER_TEMPERATURE,
        SENSOR_BURNER_HOURS,
        SENSOR_BURNER_MODULATION,
        SENSOR_BURNER_STARTS,
        SENSOR_DHW_GAS_CONSUMPTION_TODAY,
        SENSOR_DHW_GAS_CONSUMPTION_THIS_WEEK,
        SENSOR_DHW_GAS_CONSUMPTION_THIS_MONTH,
        SENSOR_DHW_GAS_CONSUMPTION_THIS_YEAR,
        SENSOR_GAS_CONSUMPTION_TODAY,
        SENSOR_GAS_CONSUMPTION_THIS_WEEK,
        SENSOR_GAS_CONSUMPTION_THIS_MONTH,
        SENSOR_GAS_CONSUMPTION_THIS_YEAR,
        # fuel cell
        SENSOR_POWER_PRODUCTION_CURRENT,
        SENSOR_POWER_PRODUCTION_TODAY,
        SENSOR_POWER_PRODUCTION_THIS_WEEK,
        SENSOR_POWER_PRODUCTION_THIS_MONTH,
        SENSOR_POWER_PRODUCTION_THIS_YEAR,
    ],
}


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Create the ViCare sensor devices."""
    if discovery_info is None:
        return

    vicare_api = hass.data[VICARE_DOMAIN][VICARE_API]
    heating_type = hass.data[VICARE_DOMAIN][VICARE_HEATING_TYPE]

    sensors = SENSORS_GENERIC.copy()

    if heating_type != HeatingType.generic:
        sensors.extend(SENSORS_BY_HEATINGTYPE[heating_type])

    add_entities(
        [
            ViCareSensor(hass.data[VICARE_DOMAIN][VICARE_NAME], vicare_api, description)
            for description in SENSOR_TYPES
            if description.key in sensors
        ]
    )


class ViCareSensor(SensorEntity):
    """Representation of a ViCare sensor."""

    entity_description: ViCareSensorEntityDescription

    def __init__(self, name, api, description: ViCareSensorEntityDescription):
        """Initialize the sensor."""
        self.entity_description = description
        self._attr_name = f"{name} {description.name}"
        self._api = api
        self._state = None

    @property
    def available(self):
        """Return True if entity is available."""
        return self._state is not None

    @property
    def unique_id(self):
        """Return a unique ID."""
        return f"{self._api.service.id}-{self.entity_description.key}"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    def update(self):
        """Update state of sensor."""
        try:
            with suppress(PyViCareNotSupportedFeatureError):
                self._state = self.entity_description.value_getter(self._api)
        except requests.exceptions.ConnectionError:
            _LOGGER.error("Unable to retrieve data from ViCare server")
        except ValueError:
            _LOGGER.error("Unable to decode data from ViCare server")
        except PyViCareRateLimitError as limit_exception:
            _LOGGER.error("Vicare API rate limit exceeded: %s", limit_exception)
