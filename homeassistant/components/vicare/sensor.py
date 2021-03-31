"""Viessmann ViCare sensor device."""
import logging

import requests

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_ICON,
    CONF_NAME,
    CONF_UNIT_OF_MEASUREMENT,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_TEMPERATURE,
    ENERGY_KILO_WATT_HOUR,
    ENERGY_WATT_HOUR,
    PERCENTAGE,
    TEMP_CELSIUS,
    TIME_HOURS,
)

from . import (
    DOMAIN as VICARE_DOMAIN,
    PYVICARE_ERROR,
    VICARE_API,
    VICARE_HEATING_TYPE,
    VICARE_NAME,
    HeatingType,
)

_LOGGER = logging.getLogger(__name__)

CONF_GETTER = "getter"

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

SENSOR_TYPES = {
    SENSOR_OUTSIDE_TEMPERATURE: {
        CONF_NAME: "Outside Temperature",
        CONF_ICON: None,
        CONF_UNIT_OF_MEASUREMENT: TEMP_CELSIUS,
        CONF_GETTER: lambda api: api.getOutsideTemperature(),
        CONF_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
    },
    SENSOR_SUPPLY_TEMPERATURE: {
        CONF_NAME: "Supply Temperature",
        CONF_ICON: None,
        CONF_UNIT_OF_MEASUREMENT: TEMP_CELSIUS,
        CONF_GETTER: lambda api: api.getSupplyTemperature(),
        CONF_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
    },
    # gas sensors
    SENSOR_BOILER_TEMPERATURE: {
        CONF_NAME: "Boiler Temperature",
        CONF_ICON: None,
        CONF_UNIT_OF_MEASUREMENT: TEMP_CELSIUS,
        CONF_GETTER: lambda api: api.getBoilerTemperature(),
        CONF_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
    },
    SENSOR_BURNER_MODULATION: {
        CONF_NAME: "Burner modulation",
        CONF_ICON: "mdi:percent",
        CONF_UNIT_OF_MEASUREMENT: PERCENTAGE,
        CONF_GETTER: lambda api: api.getBurnerModulation(),
        CONF_DEVICE_CLASS: None,
    },
    SENSOR_DHW_GAS_CONSUMPTION_TODAY: {
        CONF_NAME: "Hot water gas consumption today",
        CONF_ICON: "mdi:power",
        CONF_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
        CONF_GETTER: lambda api: api.getGasConsumptionDomesticHotWaterToday(),
        CONF_DEVICE_CLASS: None,
    },
    SENSOR_DHW_GAS_CONSUMPTION_THIS_WEEK: {
        CONF_NAME: "Hot water gas consumption this week",
        CONF_ICON: "mdi:power",
        CONF_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
        CONF_GETTER: lambda api: api.getGasConsumptionDomesticHotWaterThisWeek(),
        CONF_DEVICE_CLASS: None,
    },
    SENSOR_DHW_GAS_CONSUMPTION_THIS_MONTH: {
        CONF_NAME: "Hot water gas consumption this month",
        CONF_ICON: "mdi:power",
        CONF_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
        CONF_GETTER: lambda api: api.getGasConsumptionDomesticHotWaterThisMonth(),
        CONF_DEVICE_CLASS: None,
    },
    SENSOR_DHW_GAS_CONSUMPTION_THIS_YEAR: {
        CONF_NAME: "Hot water gas consumption this year",
        CONF_ICON: "mdi:power",
        CONF_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
        CONF_GETTER: lambda api: api.getGasConsumptionDomesticHotWaterThisYear(),
        CONF_DEVICE_CLASS: None,
    },
    SENSOR_GAS_CONSUMPTION_TODAY: {
        CONF_NAME: "Heating gas consumption today",
        CONF_ICON: "mdi:power",
        CONF_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
        CONF_GETTER: lambda api: api.getGasConsumptionHeatingToday(),
        CONF_DEVICE_CLASS: None,
    },
    SENSOR_GAS_CONSUMPTION_THIS_WEEK: {
        CONF_NAME: "Heating gas consumption this week",
        CONF_ICON: "mdi:power",
        CONF_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
        CONF_GETTER: lambda api: api.getGasConsumptionHeatingThisWeek(),
        CONF_DEVICE_CLASS: None,
    },
    SENSOR_GAS_CONSUMPTION_THIS_MONTH: {
        CONF_NAME: "Heating gas consumption this month",
        CONF_ICON: "mdi:power",
        CONF_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
        CONF_GETTER: lambda api: api.getGasConsumptionHeatingThisMonth(),
        CONF_DEVICE_CLASS: None,
    },
    SENSOR_GAS_CONSUMPTION_THIS_YEAR: {
        CONF_NAME: "Heating gas consumption this year",
        CONF_ICON: "mdi:power",
        CONF_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
        CONF_GETTER: lambda api: api.getGasConsumptionHeatingThisYear(),
        CONF_DEVICE_CLASS: None,
    },
    SENSOR_BURNER_STARTS: {
        CONF_NAME: "Burner Starts",
        CONF_ICON: "mdi:counter",
        CONF_UNIT_OF_MEASUREMENT: None,
        CONF_GETTER: lambda api: api.getBurnerStarts(),
        CONF_DEVICE_CLASS: None,
    },
    SENSOR_BURNER_HOURS: {
        CONF_NAME: "Burner Hours",
        CONF_ICON: "mdi:counter",
        CONF_UNIT_OF_MEASUREMENT: TIME_HOURS,
        CONF_GETTER: lambda api: api.getBurnerHours(),
        CONF_DEVICE_CLASS: None,
    },
    # heatpump sensors
    SENSOR_COMPRESSOR_STARTS: {
        CONF_NAME: "Compressor Starts",
        CONF_ICON: "mdi:counter",
        CONF_UNIT_OF_MEASUREMENT: None,
        CONF_GETTER: lambda api: api.getCompressorStarts(),
        CONF_DEVICE_CLASS: None,
    },
    SENSOR_COMPRESSOR_HOURS: {
        CONF_NAME: "Compressor Hours",
        CONF_ICON: "mdi:counter",
        CONF_UNIT_OF_MEASUREMENT: TIME_HOURS,
        CONF_GETTER: lambda api: api.getCompressorHours(),
        CONF_DEVICE_CLASS: None,
    },
    SENSOR_COMPRESSOR_HOURS_LOADCLASS1: {
        CONF_NAME: "Compressor Hours Load Class 1",
        CONF_ICON: "mdi:counter",
        CONF_UNIT_OF_MEASUREMENT: TIME_HOURS,
        CONF_GETTER: lambda api: api.getCompressorHoursLoadClass1(),
        CONF_DEVICE_CLASS: None,
    },
    SENSOR_COMPRESSOR_HOURS_LOADCLASS2: {
        CONF_NAME: "Compressor Hours Load Class 2",
        CONF_ICON: "mdi:counter",
        CONF_UNIT_OF_MEASUREMENT: TIME_HOURS,
        CONF_GETTER: lambda api: api.getCompressorHoursLoadClass2(),
        CONF_DEVICE_CLASS: None,
    },
    SENSOR_COMPRESSOR_HOURS_LOADCLASS3: {
        CONF_NAME: "Compressor Hours Load Class 3",
        CONF_ICON: "mdi:counter",
        CONF_UNIT_OF_MEASUREMENT: TIME_HOURS,
        CONF_GETTER: lambda api: api.getCompressorHoursLoadClass3(),
        CONF_DEVICE_CLASS: None,
    },
    SENSOR_COMPRESSOR_HOURS_LOADCLASS4: {
        CONF_NAME: "Compressor Hours Load Class 4",
        CONF_ICON: "mdi:counter",
        CONF_UNIT_OF_MEASUREMENT: TIME_HOURS,
        CONF_GETTER: lambda api: api.getCompressorHoursLoadClass4(),
        CONF_DEVICE_CLASS: None,
    },
    SENSOR_COMPRESSOR_HOURS_LOADCLASS5: {
        CONF_NAME: "Compressor Hours Load Class 5",
        CONF_ICON: "mdi:counter",
        CONF_UNIT_OF_MEASUREMENT: TIME_HOURS,
        CONF_GETTER: lambda api: api.getCompressorHoursLoadClass5(),
        CONF_DEVICE_CLASS: None,
    },
    SENSOR_RETURN_TEMPERATURE: {
        CONF_NAME: "Return Temperature",
        CONF_ICON: None,
        CONF_UNIT_OF_MEASUREMENT: TEMP_CELSIUS,
        CONF_GETTER: lambda api: api.getReturnTemperature(),
        CONF_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
    },
    # fuelcell sensors
    SENSOR_POWER_PRODUCTION_CURRENT: {
        CONF_NAME: "Power production current",
        CONF_ICON: None,
        CONF_UNIT_OF_MEASUREMENT: ENERGY_WATT_HOUR,
        CONF_GETTER: lambda api: api.getPowerProductionCurrent(),
        CONF_DEVICE_CLASS: DEVICE_CLASS_ENERGY,
    },
    SENSOR_POWER_PRODUCTION_TODAY: {
        CONF_NAME: "Power production today",
        CONF_ICON: None,
        CONF_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
        CONF_GETTER: lambda api: api.getPowerProductionToday(),
        CONF_DEVICE_CLASS: DEVICE_CLASS_ENERGY,
    },
    SENSOR_POWER_PRODUCTION_THIS_WEEK: {
        CONF_NAME: "Power production this week",
        CONF_ICON: None,
        CONF_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
        CONF_GETTER: lambda api: api.getPowerProductionThisWeek(),
        CONF_DEVICE_CLASS: DEVICE_CLASS_ENERGY,
    },
    SENSOR_POWER_PRODUCTION_THIS_MONTH: {
        CONF_NAME: "Power production this month",
        CONF_ICON: None,
        CONF_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
        CONF_GETTER: lambda api: api.getPowerProductionThisMonth(),
        CONF_DEVICE_CLASS: DEVICE_CLASS_ENERGY,
    },
    SENSOR_POWER_PRODUCTION_THIS_YEAR: {
        CONF_NAME: "Power production this year",
        CONF_ICON: None,
        CONF_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
        CONF_GETTER: lambda api: api.getPowerProductionThisYear(),
        CONF_DEVICE_CLASS: DEVICE_CLASS_ENERGY,
    },
}

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
            ViCareSensor(hass.data[VICARE_DOMAIN][VICARE_NAME], vicare_api, sensor)
            for sensor in sensors
        ]
    )


class ViCareSensor(SensorEntity):
    """Representation of a ViCare sensor."""

    def __init__(self, name, api, sensor_type):
        """Initialize the sensor."""
        self._sensor = SENSOR_TYPES[sensor_type]
        self._name = f"{name} {self._sensor[CONF_NAME]}"
        self._api = api
        self._sensor_type = sensor_type
        self._state = None

    @property
    def available(self):
        """Return True if entity is available."""
        return self._state is not None and self._state != PYVICARE_ERROR

    @property
    def unique_id(self):
        """Return a unique ID."""
        return f"{self._api.service.id}-{self._sensor_type}"

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._sensor[CONF_ICON]

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._sensor[CONF_UNIT_OF_MEASUREMENT]

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return self._sensor[CONF_DEVICE_CLASS]

    def update(self):
        """Update state of sensor."""
        try:
            self._state = self._sensor[CONF_GETTER](self._api)
        except requests.exceptions.ConnectionError:
            _LOGGER.error("Unable to retrieve data from ViCare server")
        except ValueError:
            _LOGGER.error("Unable to decode data from ViCare server")
