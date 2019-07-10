"""
Support for the Environment Canada weather service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.environment_canada/
"""
import datetime
import logging
import re

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    TEMP_CELSIUS, CONF_NAME, CONF_LATITUDE, CONF_LONGITUDE, ATTR_ATTRIBUTION,
    ATTR_LOCATION, ATTR_HIDDEN)
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
import homeassistant.util.dt as dt
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

ATTR_UPDATED = 'updated'
ATTR_STATION = 'station'
ATTR_DETAIL = 'alert detail'
ATTR_TIME = 'alert time'

CONF_ATTRIBUTION = "Data provided by Environment Canada"
CONF_STATION = 'station'
CONF_LANGUAGE = 'language'

MIN_TIME_BETWEEN_UPDATES = datetime.timedelta(minutes=1)


def validate_station(station):
    """Check that the station ID is well-formed."""
    if station is None:
        return
    if not re.fullmatch(r'[A-Z]{2}/s0000\d{3}', station):
        raise vol.error.Invalid('Station ID must be of the form "XX/s0000###"')
    return station


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_LANGUAGE, default='english'):
        vol.In(['english', 'french']),
    vol.Optional(CONF_NAME): cv.string,
    vol.Optional(CONF_STATION): validate_station,
    vol.Inclusive(CONF_LATITUDE, 'latlon'): cv.latitude,
    vol.Inclusive(CONF_LONGITUDE, 'latlon'): cv.longitude,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Environment Canada sensor."""
    from env_canada import ECData

    if config.get(CONF_STATION):
        ec_data = ECData(station_id=config[CONF_STATION],
                         language=config.get(CONF_LANGUAGE))
    elif config.get(CONF_LATITUDE) and config.get(CONF_LONGITUDE):
        ec_data = ECData(coordinates=(config[CONF_LATITUDE],
                                      config[CONF_LONGITUDE]),
                         language=config.get(CONF_LANGUAGE))
    else:
        ec_data = ECData(coordinates=(hass.config.latitude,
                                      hass.config.longitude),
                         language=config.get(CONF_LANGUAGE))

    sensor_list = list(ec_data.conditions.keys()) + list(ec_data.alerts.keys())
    add_devices([ECSensor(sensor_type,
                          ec_data,
                          config.get(CONF_NAME))
                 for sensor_type in sensor_list],
                True)


class ECSensor(Entity):
    """Implementation of an Environment Canada sensor."""

    def __init__(self, sensor_type, ec_data, platform_name):
        """Initialize the sensor."""
        self.sensor_type = sensor_type
        self.ec_data = ec_data
        self._state = None
        self._attr = None
        self._data = None
        self._name = None
        self._unit = None

        if platform_name:
            self.entity_id = 'sensor.' + '_'.join([platform_name, sensor_type])
        else:
            self.entity_id = 'sensor.' + sensor_type

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        return self._attr

    @property
    def unit_of_measurement(self):
        """Return the units of measurement."""
        return self._unit

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Update current conditions."""
        self.ec_data.update()
        self.ec_data.conditions.update(self.ec_data.alerts)

        conditions = self.ec_data.conditions
        metadata = self.ec_data.metadata
        sensor_data = conditions.get(self.sensor_type)

        self._attr = {}
        self._name = sensor_data.get('label')
        value = sensor_data.get('value')

        if isinstance(value, list):
            self._state = ' | '.join([str(s.get('title'))
                                      for s in value])
            self._attr.update({
                ATTR_DETAIL: ' | '.join([str(s.get('detail'))
                                         for s in value]),
                ATTR_TIME: ' | '.join([str(s.get('date'))
                                       for s in value])
            })
        else:
            self._state = value

        if sensor_data.get('unit') == 'C':
            self._unit = TEMP_CELSIUS
        else:
            self._unit = sensor_data.get('unit')

        timestamp = metadata.get('timestamp')
        if timestamp:
            updated_utc = datetime.datetime.strptime(timestamp, '%Y%m%d%H%M%S')
            updated_local = dt.as_local(updated_utc).isoformat()
        else:
            updated_local = None

        hidden = bool(self._state is None or self._state == '')

        self._attr.update({
            ATTR_ATTRIBUTION: CONF_ATTRIBUTION,
            ATTR_UPDATED: updated_local,
            ATTR_LOCATION: metadata.get('location'),
            ATTR_STATION: metadata.get('station'),
            ATTR_HIDDEN: hidden
        })
