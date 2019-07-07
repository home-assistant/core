"""Support for WWLLN Weather Station sensors."""
import logging

from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE
from homeassistant.util.dt import utc_from_timestamp

from . import (
    SENSOR_TYPES, TYPE_NEAREST_STRIKE_DISTANCE, TYPE_NUM_NEARBY_STRIKES,
    WWLLNEntity)
from .const import DATA_CLIENT, DOMAIN

_LOGGER = logging.getLogger(__name__)

ATTR_TIMESTAMP = 'timestamp'


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up WWLLN sensors based on a config entry."""
    wwlln = hass.data[DOMAIN][DATA_CLIENT][entry.entry_id]

    sensor_list = []
    for sensor_type, attrs in SENSOR_TYPES.items():
        name, icon, unit = attrs
        sensor_list.append(WWLLNSensor(wwlln, sensor_type, name, icon, unit))

    async_add_entities(sensor_list, True)


class WWLLNSensor(WWLLNEntity):
    """Define an WWLLN sensor."""

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    async def async_update(self):
        """Fetch new state data for the sensor."""
        if self._sensor_type == TYPE_NEAREST_STRIKE_DISTANCE:
            self._attrs.update({
                ATTR_LATITUDE: self._wwlln.nearest_strike['lat'],
                ATTR_LONGITUDE: self._wwlln.nearest_strike['long'],
                ATTR_TIMESTAMP: utc_from_timestamp(
                    self._wwlln.nearest_strike['unixTime']),
            })
            self._state = round(self._wwlln.nearest_strike['distance'], 2)
        elif self._sensor_type == TYPE_NUM_NEARBY_STRIKES:
            self._state = len(self._wwlln.nearby_strikes)
