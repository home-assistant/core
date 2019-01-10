"""
Support for hydrological data from the Federal Office for the Environment FOEN.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.swiss_hydrological_data/
"""
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import ATTR_ATTRIBUTION, CONF_MONITORED_CONDITIONS
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

REQUIREMENTS = ['swisshydrodata==0.0.3']

_LOGGER = logging.getLogger(__name__)

ATTRIBUTION = "Data provided by the Swiss Federal Office for the " \
              "Environment FOEN"

ATTR_DELTA_24H = 'delta-24h'
ATTR_MAX_1H = 'max-1h'
ATTR_MAX_24H = 'max-24h'
ATTR_MEAN_1H = 'mean-1h'
ATTR_MEAN_24H = 'mean-24h'
ATTR_MIN_1H = 'min-1h'
ATTR_MIN_24H = 'min-24h'
ATTR_PREVIOUS_24H = 'previous-24h'
ATTR_STATION = 'station'
ATTR_STATION_UPDATE = 'station_update'
ATTR_WATER_BODY = 'water_body'
ATTR_WATER_BODY_TYPE = 'water_body_type'

CONF_STATION = 'station'

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)

SENSOR_DISCHARGE = 'discharge'
SENSOR_LEVEL = 'level'
SENSOR_TEMPERATURE = 'temperature'

CONDITIONS = {
    SENSOR_DISCHARGE: 'mdi:waves',
    SENSOR_LEVEL: 'mdi:zodiac-aquarius',
    SENSOR_TEMPERATURE: 'mdi:oil-temperature',
}

CONDITION_DETAILS = [
    ATTR_DELTA_24H,
    ATTR_MAX_1H,
    ATTR_MAX_24H,
    ATTR_MEAN_1H,
    ATTR_MEAN_24H,
    ATTR_MIN_1H,
    ATTR_MIN_24H,
    ATTR_PREVIOUS_24H,
]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_STATION): vol.Coerce(int),
    vol.Optional(CONF_MONITORED_CONDITIONS, default=[SENSOR_TEMPERATURE]):
        vol.All(cv.ensure_list, [vol.In(CONDITIONS)]),
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Swiss hydrological sensor."""
    station = config.get(CONF_STATION)
    monitored_conditions = config.get(CONF_MONITORED_CONDITIONS)

    hydro_data = HydrologicalData(station)
    hydro_data.update()

    if hydro_data.data is None:
        _LOGGER.error("The station doesn't exists: %s", station)
        return

    entities = []

    for condition in monitored_conditions:
        entities.append(
            SwissHydrologicalDataSensor(hydro_data, station, condition))

    add_entities(entities, True)


class SwissHydrologicalDataSensor(Entity):
    """Implementation of a Swiss hydrological sensor."""

    def __init__(self, hydro_data, station, condition):
        """Initialize the Swiss hydrological sensor."""
        self.hydro_data = hydro_data
        self._condition = condition
        self._data = self._state = self._unit_of_measurement = None
        self._icon = CONDITIONS[condition]
        self._station = station

    @property
    def name(self):
        """Return the name of the sensor."""
        return "{0} {1}".format(self._data['water-body-name'], self._condition)

    @property
    def unique_id(self) -> str:
        """Return a unique, friendly identifier for this entity."""
        return '{0}_{1}'.format(self._station, self._condition)

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        if self._state is not None:
            return self.hydro_data.data['parameters'][self._condition]['unit']
        return None

    @property
    def state(self):
        """Return the state of the sensor."""
        if isinstance(self._state, (int, float)):
            return round(self._state, 2)
        return None

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        attrs = {}

        if not self._data:
            attrs[ATTR_ATTRIBUTION] = ATTRIBUTION
            return attrs

        attrs[ATTR_WATER_BODY_TYPE] = self._data['water-body-type']
        attrs[ATTR_STATION] = self._data['name']
        attrs[ATTR_STATION_UPDATE] = \
            self._data['parameters'][self._condition]['datetime']
        attrs[ATTR_ATTRIBUTION] = ATTRIBUTION

        for entry in CONDITION_DETAILS:
            attrs[entry.replace('-', '_')] = \
                self._data['parameters'][self._condition][entry]

        return attrs

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return self._icon

    def update(self):
        """Get the latest data and update the state."""
        self.hydro_data.update()
        self._data = self.hydro_data.data

        if self._data is None:
            self._state = None
        else:
            self._state = self._data['parameters'][self._condition]['value']


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
