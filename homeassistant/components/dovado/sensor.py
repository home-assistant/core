"""Support for sensors from the Dovado router."""
from datetime import timedelta
import logging
import re

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_SENSORS
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

from . import DOMAIN as DOVADO_DOMAIN

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=30)

SENSOR_UPLOAD = 'upload'
SENSOR_DOWNLOAD = 'download'
SENSOR_SIGNAL = 'signal'
SENSOR_NETWORK = 'network'
SENSOR_SMS_UNREAD = 'sms'

SENSORS = {
    SENSOR_NETWORK: ('signal strength', 'Network', None,
                     'mdi:access-point-network'),
    SENSOR_SIGNAL: ('signal strength', 'Signal Strength', '%', 'mdi:signal'),
    SENSOR_SMS_UNREAD: ('sms unread', 'SMS unread', '',
                        'mdi:message-text-outline'),
    SENSOR_UPLOAD: ('traffic modem tx', 'Sent', 'GB', 'mdi:cloud-upload'),
    SENSOR_DOWNLOAD: ('traffic modem rx', 'Received', 'GB',
                      'mdi:cloud-download'),
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_SENSORS): vol.All(cv.ensure_list, [vol.In(SENSORS)]),
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Dovado sensor platform."""
    dovado = hass.data[DOVADO_DOMAIN]

    entities = []
    for sensor in config[CONF_SENSORS]:
        entities.append(DovadoSensor(dovado, sensor))

    add_entities(entities)


class DovadoSensor(Entity):
    """Representation of a Dovado sensor."""

    def __init__(self, data, sensor):
        """Initialize the sensor."""
        self._data = data
        self._sensor = sensor
        self._state = self._compute_state()

    def _compute_state(self):
        """Compute the state of the sensor."""
        state = self._data.state.get(SENSORS[self._sensor][0])
        if self._sensor == SENSOR_NETWORK:
            match = re.search(r"\((.+)\)", state)
            return match.group(1) if match else None
        if self._sensor == SENSOR_SIGNAL:
            try:
                return int(state.split()[0])
            except ValueError:
                return None
        if self._sensor == SENSOR_SMS_UNREAD:
            return int(state)
        if self._sensor in [SENSOR_UPLOAD, SENSOR_DOWNLOAD]:
            return round(float(state) / 1e6, 1)
        return state

    def update(self):
        """Update sensor values."""
        self._data.update()
        self._state = self._compute_state()

    @property
    def name(self):
        """Return the name of the sensor."""
        return "{} {}".format(self._data.name, SENSORS[self._sensor][1])

    @property
    def state(self):
        """Return the sensor state."""
        return self._state

    @property
    def icon(self):
        """Return the icon for the sensor."""
        return SENSORS[self._sensor][3]

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return SENSORS[self._sensor][2]

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {k: v for k, v in self._data.state.items()
                if k not in ['date', 'time']}
