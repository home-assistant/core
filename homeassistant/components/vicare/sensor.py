"""Viessmann ViCare sensor device."""
import logging

import requests

from homeassistant.const import (
    CONF_ICON,
    CONF_NAME,
    CONF_UNIT_OF_MEASUREMENT,
    TEMP_CELSIUS,
)
from homeassistant.helpers.entity import Entity

from . import (
    DOMAIN as VICARE_DOMAIN,
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

# heatpump sensors
SENSOR_COMPRESSOR_STARTS = "compressor_starts"
SENSOR_COMPRESSOR_HOURS = "compressor_hours"

SENSOR_TYPES = {
    SENSOR_OUTSIDE_TEMPERATURE: {
        CONF_NAME: "Outside Temperature",
        CONF_ICON: "mdi:thermometer",
        CONF_UNIT_OF_MEASUREMENT: TEMP_CELSIUS,
        CONF_GETTER: lambda api: api.getOutsideTemperature(),
    },
    SENSOR_SUPPLY_TEMPERATURE: {
        CONF_NAME: "Supply Temperature",
        CONF_ICON: "mdi:thermometer",
        CONF_UNIT_OF_MEASUREMENT: TEMP_CELSIUS,
        CONF_GETTER: lambda api: api.getSupplyTemperature(),
    },
    # gas sensors
    SENSOR_BOILER_TEMPERATURE: {
        CONF_NAME: "Boiler Temperature",
        CONF_ICON: "mdi:thermometer",
        CONF_UNIT_OF_MEASUREMENT: TEMP_CELSIUS,
        CONF_GETTER: lambda api: api.getBoilerTemperature(),
    },
    # heatpump sensors
    SENSOR_COMPRESSOR_STARTS: {
        CONF_NAME: "Compressor Starts",
        CONF_ICON: "mdi:counter",
        CONF_UNIT_OF_MEASUREMENT: None,
        CONF_GETTER: lambda api: api.getCompressorStarts(),
    },
    SENSOR_COMPRESSOR_HOURS: {
        CONF_NAME: "Compressor Hours",
        CONF_ICON: "mdi:counter",
        CONF_UNIT_OF_MEASUREMENT: None,
        CONF_GETTER: lambda api: api.getCompressorHours(),
    },
    SENSOR_RETURN_TEMPERATURE: {
        CONF_NAME: "Return Temperature",
        CONF_ICON: "mdi:thermometer",
        CONF_UNIT_OF_MEASUREMENT: TEMP_CELSIUS,
        CONF_GETTER: lambda api: api.getReturnTemperature(),
    },
}

SENSORS_GENERIC = [SENSOR_OUTSIDE_TEMPERATURE, SENSOR_SUPPLY_TEMPERATURE]

SENSORS_BY_HEATINGTYPE = {
    HeatingType.gas: [
        SENSOR_BOILER_TEMPERATURE
    ],  # TODO: add additional gas sensors (consumption, etc.)
    HeatingType.heatpump: [
        SENSOR_COMPRESSOR_HOURS,
        SENSOR_COMPRESSOR_STARTS,
        SENSOR_RETURN_TEMPERATURE,
    ],
}


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Create the ViCare sensor devices."""
    if discovery_info is None:
        return

    vicare_api = hass.data[VICARE_DOMAIN][VICARE_API]
    heating_type = hass.data[VICARE_DOMAIN][VICARE_HEATING_TYPE]

    sensors = SENSORS_GENERIC

    if heating_type != HeatingType.generic:
        sensors.extend(SENSORS_BY_HEATINGTYPE[heating_type])

    add_entities(
        [
            ViCareSensor(hass.data[VICARE_DOMAIN][VICARE_NAME], vicare_api, sensor)
            for sensor in sensors
        ]
    )


class ViCareSensor(Entity):
    """Representation of a ViCare sensor."""

    def __init__(self, name, api, type):
        """Initialize the sensor."""
        self._sensor = SENSOR_TYPES[type]
        self._name = f"{name} {self._sensor[CONF_NAME]}"
        self._api = api
        self._type = type
        self._state = None

    @property
    def unique_id(self):
        """Return a unique ID."""
        return f"{self._api.service.id}-{self._type}"

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

    def update(self):
        """Update state of sensor."""
        try:
            self._state = self._sensor[CONF_GETTER](self._api)
        except requests.exceptions.ConnectionError:
            _LOGGER.error("Unable to retrieve data from ViCare server")
        except ValueError:
            _LOGGER.error("Unable to decode data from ViCare server")
