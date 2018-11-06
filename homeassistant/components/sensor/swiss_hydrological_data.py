"""
Support for hydrological data from the Federal Office for the Environment FOEN.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.swiss_hydrological_data/
"""
import logging
from datetime import timedelta

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import STATE_UNKNOWN
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

REQUIREMENTS = ['swisshydrodata==0.0.3']

_LOGGER = logging.getLogger(__name__)

CONF_STATION = 'station'
CONF_MONITORED_CONDITIONS = 'monitored_conditions'
CONF_ATTRIBUTION = "Data provided by the Swiss Federal Office for the " \
                   "Environment FOEN"

DEFAULT_NAME = 'SwissHydroData'

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)

# https://developers.home-assistant.io/docs/en/development_validation.html

CONDITIONS = [
    "value",
    "previous-24h",
    "delta-24h",
    "max-24h",
    "mean-24h",
    "min-24h",
    "max-1h",
    "mean-1h",
    "min-1h"]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_STATION): vol.Coerce(int),
    vol.Required(CONF_MONITORED_CONDITIONS): vol.Schema({
        "temperature": vol.All(cv.ensure_list, [vol.In(CONDITIONS)]),
        "level": vol.All(cv.ensure_list, [vol.In(CONDITIONS)]),
        "discharge": vol.All(cv.ensure_list, [vol.In(CONDITIONS)])
    })
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Swiss hydrological sensor."""
    station = config.get(CONF_STATION)
    monitored_conditions = config.get(CONF_MONITORED_CONDITIONS)

    hydro_data = HydrologicalData(station)
    hydro_data.update()

    entities = []

    for condition in monitored_conditions:
        for value in monitored_conditions[condition]:
            entities.append(
                SwissHydrologicalDataSensor(
                    hydro_data, station, condition, value)
            )

    add_entities(entities, True)


class SwissHydrologicalDataSensor(Entity):
    """Implementation of an Swiss hydrological sensor."""

    def __init__(self, hydro_data, station, condition, value):
        """Initialize the sensor."""
        self.hydro_data = hydro_data
        self._station = station
        self._name = None
        self._condition = condition
        self._value = value
        self._unit_of_measurement = None
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return "{0} {1} {2}".format(
            self._station,
            self._condition,
            self._value)

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        if self._state is not STATE_UNKNOWN:
            return self.hydro_data.data["parameters"][self._condition]["unit"]
        return None

    @property
    def state(self):
        """Return the state of the sensor."""
        if isinstance(self._state, (int, float)):
            return round(self._state, 2)
        return STATE_UNKNOWN

    @property
    def state_attributes(self):
        """Return the state attributes."""
        if not self.hydro_data.data:
            return {"ATTR_ATTRIBUTION": CONF_ATTRIBUTION}
        return {
            "ATTR_WATER_BODY": self.hydro_data.data["water-body-name"],
            "ATTR_WATER_BODY_TYPE": self.hydro_data.data["water-body-type"],
            "ATTR_STATION": self.hydro_data.data["name"],
            "ATTR_UPDATE":
            self.hydro_data.data["parameters"][self._condition]["datetime"],
            "ATTR_ATTRIBUTION": CONF_ATTRIBUTION
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
            if key in self._condition:
                return val

    def update(self):
        """Get the latest data and update the state."""
        self.hydro_data.update()
        data = self.hydro_data.data
        if data is None:
            self._state = STATE_UNKNOWN
        else:
            self._state = data["parameters"][self._condition][self._value]


class HydrologicalData:
    """The Class for handling the data retrieval."""

    def __init__(self, station):
        """Initialize the data object."""
        self.station = station
        self.data = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data."""
        from swisshydrodata import SwissHydroData

        shd = SwissHydroData()
        self.data = shd.get_station(self.station)
