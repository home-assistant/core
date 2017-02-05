"""
Support for KWB Easyfire.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.kwb/
"""
import logging

import voluptuous as vol

from homeassistant.const import (CONF_HOST, CONF_PORT)
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['pykwb==0.0.5']

_LOGGER = logging.getLogger(__name__)

DEFAULT_HOST = 'localhost'
DEFAULT_PORT = 23
DEFAULT_TYPE = 'tcp'
DEFAULT_RAW = 'off'

MODE_SERIAL = 0
MODE_TCP = 1

CONF_TYPE = 'type'
CONF_RAW = 'raw'

SERIAL_SCHEMA = {
    vol.Required(CONF_PORT): cv.string,
    vol.Required(CONF_TYPE): 'serial',
    vol.Optional(CONF_TYPE): 'raw',
}

ETHERNET_SCHEMA = {
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_PORT): cv.positive_int,
    vol.Required(CONF_TYPE): 'tcp',
    vol.Optional(CONF_TYPE): 'raw',
}


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the KWB component."""
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    connection_type = config.get(CONF_TYPE)
    raw = config.get(CONF_RAW)

    if raw == 'on':
        raw = True

    from pykwb import kwb

    _LOGGER.info('KWB: initializing')

    if connection_type == 'serial':
        easyfire = kwb.KWBEasyfire(MODE_SERIAL, "", 0, port)
    elif connection_type == 'tcp':
        easyfire = kwb.KWBEasyfire(MODE_TCP, host, port)
    else:
        return False

    sensors = []
    for sensor in easyfire.get_sensors():
        if ((sensor.sensor_type != kwb.PROP_SENSOR_RAW)
                or (sensor.sensor_type == kwb.PROP_SENSOR_RAW and raw)):
            sensors.append(KWBSensor(easyfire, sensor))

    add_devices(sensors)

    _LOGGER.info('KWB: starting thread')
    easyfire.run_thread()
    _LOGGER.info('KWB: thread started')


class KWBSensor(Entity):
    """Representation of a KWB Easyfire sensor."""

    def __init__(self, easyfire, sensor):
        """Initialize the KWB sensor."""
        self._easyfire = easyfire
        self._sensor = sensor
        self._client_name = "KWB"
        self._name = self._sensor.name

    @property
    def name(self):
        """Return the name."""
        return '{} {}'.format(self._client_name, self._name)

    @property
    def state(self):
        """Return the state of value."""
        return self._sensor.value

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._sensor.unit_of_measurement
