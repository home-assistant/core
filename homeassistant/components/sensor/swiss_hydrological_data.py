"""
Support for hydrological data from the Federal Office for the Environment FOEN.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.swiss_hydrological_data/
"""
import logging
from datetime import timedelta

import voluptuous as vol
import requests

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_NAME, STATE_UNKNOWN, ATTR_ATTRIBUTION)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

REQUIREMENTS = ['swisshydrodata==0.0.2']

_LOGGER = logging.getLogger(__name__)

CONF_STATION = 'station'
CONF_MEASUREMENTS = 'measurements'
CONF_ATTRIBUTION = "Data provided by the Swiss Federal Office for the " \
                   "Environment FOEN"

DEFAULT_NAME = 'SwissHydroData'

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=30)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_STATION): vol.Coerce(int),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONF_MEASUREMENTS): vol.Any([
        'temperature',
        'level',
        'discharge',
        'min_temperature',
        'min_level',
        'min_discharge',
        'max_temperature',
        'max_level',
        'max_discharge',
        'mean_temperature',
        'mean_level',
        'mean_discharge'
    ])
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Swiss hydrological sensor."""
    name = config.get(CONF_NAME)
    station = config.get(CONF_STATION)
    measurements = config.get(CONF_MEASUREMENTS)

    data = HydrologicalData(station)

    response = requests.get(
        "https://www.hydrodaten.admin.ch/en/{0}.html".format(station),
        timeout=5
    )
    if response.status_code != 200:
        _LOGGER.error("The given station does not exist: %s", station)
        return False

    entities = []
    for measurement in measurements:
        entities.append(SwissHydrologicalDataSensor(name, data, measurement))

    add_entities(entities, True)


class SwissHydrologicalDataSensor(Entity):
    """Implementation of an Swiss hydrological sensor."""

    def __init__(self, name, data, measurement):
        """Initialize the sensor."""
        self.data = data
        self._name = name
        self._measurement = measurement
        self._unit_of_measurement = None
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        if not self._name:
            self._name = "SwissHydroData"
        return "{0}_{1}".format(self._name, self._measurement)

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        if self._state is not STATE_UNKNOWN:
            return self.data.measurements[self._measurement]["unit"]
        return None

    @property
    def state(self):
        """Return the state of the sensor."""
        try:
            return round(self._state, 2)
        except ValueError:
            return STATE_UNKNOWN

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_ATTRIBUTION: CONF_ATTRIBUTION
        }

    @property
    def icon(self):
        """Icon to use in the frontend."""
        icons = {
            "temperature": "mdi:oil-temperature",
            "level": "mdi:zodiac-aquarius",
            "discharge": "mdi:waves"
        }
        for key, val in icons.items():
            if key in self._measurement:
                return val

    def update(self):
        """Get the latest data and update the state."""
        self.data.update()
        if self.data.measurements is None:
            self._state = STATE_UNKNOWN
        else:
            self._state = self.data.measurements[self._measurement]["value"]


class HydrologicalData:
    """The Class for handling the data retrieval."""

    def __init__(self, station):
        """Initialize the data object."""
        self.station = station
        self.measurements = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from hydrodata.ch."""
        from swisshydrodata import SwissHydroData

        data = {}

        shd = SwissHydroData()
        shd.load_station_data(self.station)

        data["temperature"] = shd.get_latest_temperature()
        data["level"] = shd.get_latest_level()
        data["discharge"] = shd.get_latest_discharge()
        data["min_temperature"] = shd.get_min_temperature()
        data["min_level"] = shd.get_min_level()
        data["min_discharge"] = shd.get_min_discharge()
        data["max_temperature"] = shd.get_max_temperature()
        data["max_level"] = shd.get_max_level()
        data["max_discharge"] = shd.get_max_discharge()
        data["mean_temperature"] = shd.get_mean_temperature()
        data["mean_level"] = shd.get_mean_level()
        data["mean_discharge"] = shd.get_mean_discharge()

        self.measurements = data
