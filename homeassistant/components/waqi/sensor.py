"""
Sensor platform for the WAQI Component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.waqi/
"""
import logging

from homeassistant.components.waqi import SCAN_INTERVAL
from homeassistant.const import (ATTR_ATTRIBUTION, ATTR_TIME, ATTR_TEMPERATURE,
                                 TEMP_CELSIUS)
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

ATTR_HUMIDITY = 'humidity'
ATTR_PRESSURE = 'pressure'
ATTR_RAIN = 'rain'
ATTR_WIND = 'wind speed'

_LOGGER = logging.getLogger(__name__)

SENSORS = {'temperature': ['t', ATTR_TEMPERATURE, 'mdi:thermometer',
                           TEMP_CELSIUS],
           'humidity': ['h', ATTR_HUMIDITY, 'mdi:water-percent', '%'],
           'pressure': ['p', ATTR_PRESSURE, None, 'mbar'],
           'rain': ['r', ATTR_RAIN, 'weather-rainy', 'mm'],
           'wind': ['w', ATTR_WIND, 'weather-windy', 'km/h']}


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the requested World Air Quality Index sensors."""
    devs = []
    data = discovery_info['data']

    for sensor, options in SENSORS.items():
        # Not all locations have all data available, only bring up sensors with
        # available data
        if data.get(options[0]):
            devs.append(WaqiSensor(data, sensor, options))
    async_add_entities(devs, True)


class WaqiSensor(Entity):
    """Representation of a Sensor."""

    def __init__(self, data, sensor, options):
        """Initialize the sensor."""
        self.waqi_data = data
        self._data = data.data
        self._state = None
        self._type = sensor
        self._key = options[0]
        self._attr = options[1]
        self._icon = options[2]
        self._unit = options[3]
        self.uid = self.waqi_data.station['uid']
        self.url = self.waqi_data.station['station']['url']
        self.station_name = self.waqi_data.station['station']['name']

    @property
    def attribution(self):
        """Return the attribution."""
        return self.waqi_data.attribution

    @property
    def icon(self):
        """Return the icon to display."""
        return self._icon

    @property
    def name(self):
        """Return the name of the entity."""
        if self.station_name:
            return 'WAQI {} {}'.format(self.station_name, self._attr)
        return 'WAQI {}'.format(self.url if self.url else self.uid)

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.waqi_data.get(self._key)

    @property
    def update_time(self):
        """Return the update time."""
        return self.waqi_data.update_time

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {ATTR_ATTRIBUTION: self.attribution,
                ATTR_TIME: self.update_time}

    @Throttle(SCAN_INTERVAL)
    async def async_update(self):
        """Get the latest data and updates the states."""
        await self.waqi_data.async_update()
