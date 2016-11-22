"""
Support for the World Air Quality Index service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.waqi/
"""
import logging
from datetime import timedelta
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA
from homeassistant.helpers import config_validation as cv
import voluptuous as vol

REQUIREMENTS = ["pwaqi==1.2"]

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES = {
    'aqi':          ['AQI', '0-300+', 'mdi:cloud']
}

ATTR_LOCATION = 'locations'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(ATTR_LOCATION): cv.ensure_list
})

# Return cached results if last scan was less then this time ago
MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=30)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the requested World Air Quality Index locations."""
    dev = []
    import pwaqi
    # Iterate each module
    for location_name in config[ATTR_LOCATION]:
        _LOGGER.debug('Adding location %s', location_name)
        station_ids = pwaqi.findStationCodesByCity(location_name)
        _LOGGER.debug('I got the following stations: %s', station_ids)
        for station in station_ids:
            dev.append(WaqiSensor(station))

    add_devices(dev)


# pylint: disable=too-few-public-methods
class WaqiSensor(Entity):
    """Implementation of a WAQI sensor."""

    def __init__(self, station_id):
        """Initialize the sensor."""
        self._station_id = station_id
        self._state = None
        self.update()

    @property
    def name(self):
        """Return the name of the sensor."""
        if 'city' in self._data:
            return "WAQI {}".format(self._data['city']['name'])
        return "WAQI {}".format(self._station_id)

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return "mdi:cloud"

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return "AQI"

    @property
    def state_attributes(self):
        """Return the state attributes of the last update."""
        return {
            "time": self._data.get('time', 'no data'),
            "dominentpol": self._data.get('dominentpol', 'no data')
        }

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the data from World Air Quality Index and updates the states."""
        import pwaqi
        try:
            self._data = pwaqi.getStationObservation(self._station_id)

            self._state = self._data.get('aqi', 'no data')
        except KeyError:
            _LOGGER.exception('Unable to fetch data from WAQI.')
