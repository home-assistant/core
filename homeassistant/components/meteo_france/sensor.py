"""Support for Meteo-France raining forecast sensor."""
import logging

from homeassistant.const import ATTR_ATTRIBUTION, CONF_MONITORED_CONDITIONS
from homeassistant.helpers.entity import Entity

from . import ATTRIBUTION, CONF_CITY, DATA_METEO_FRANCE, SENSOR_TYPES

_LOGGER = logging.getLogger(__name__)

STATE_ATTR_FORECAST = '1h rain forecast'


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Meteo-France sensor."""
    if discovery_info is None:
        return

    city = discovery_info[CONF_CITY]
    monitored_conditions = discovery_info[CONF_MONITORED_CONDITIONS]
    client = hass.data[DATA_METEO_FRANCE][city]

    add_entities([MeteoFranceSensor(variable, client)
                  for variable in monitored_conditions], True)


class MeteoFranceSensor(Entity):
    """Representation of a Meteo-France sensor."""

    def __init__(self, condition, client):
        """Initialize the Meteo-France sensor."""
        self._condition = condition
        self._client = client
        self._state = None
        self._data = {}

    @property
    def name(self):
        """Return the name of the sensor."""
        return "{} {}".format(
            self._data['name'], SENSOR_TYPES[self._condition][0])

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        if self._condition == 'next_rain' and 'rain_forecast' in self._data:
            return {
                **{STATE_ATTR_FORECAST: self._data['rain_forecast']},
                ** self._data['next_rain_intervals'],
                **{ATTR_ATTRIBUTION: ATTRIBUTION}
            }
        return {ATTR_ATTRIBUTION: ATTRIBUTION}

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return SENSOR_TYPES[self._condition][1]

    def update(self):
        """Fetch new state data for the sensor."""
        try:
            self._client.update()
            self._data = self._client.get_data()
            self._state = self._data[self._condition]
        except KeyError:
            _LOGGER.error("No condition %s for location %s",
                          self._condition, self._data['name'])
            self._state = None
