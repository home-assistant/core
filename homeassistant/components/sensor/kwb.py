"""
Support for KWB Easyfire.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.kwb/
"""
import logging

import voluptuous as vol

from homeassistant.const import (CONF_HOST, CONF_PORT, CONF_DEVICE,
                                 CONF_NAME, EVENT_HOMEASSISTANT_STOP,
                                 STATE_UNKNOWN)
from homeassistant.helpers.entity import Entity
from homeassistant.components.sensor import PLATFORM_SCHEMA
import homeassistant.helpers.config_validation as cv


REQUIREMENTS = ['pykwb==0.0.8']

_LOGGER = logging.getLogger(__name__)

DEFAULT_HOST = 'localhost'
DEFAULT_PORT = 23
DEFAULT_TYPE = 'tcp'
DEFAULT_RAW = False
DEFAULT_DEVICE = '/dev/ttyUSB0'
DEFAULT_NAME = 'KWB'

MODE_SERIAL = 0
MODE_TCP = 1

CONF_TYPE = 'type'
CONF_RAW = 'raw'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_TYPE, default=DEFAULT_TYPE): vol.In(['tcp', 'serial']),
    vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Optional(CONF_DEVICE, default=DEFAULT_DEVICE): cv.string,
    vol.Optional(CONF_RAW, default=DEFAULT_RAW): cv.boolean,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the KWB component."""
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    device = config.get(CONF_DEVICE)
    connection_type = config.get(CONF_TYPE)
    raw = config.get(CONF_RAW)
    client_name = config.get(CONF_NAME)

    from pykwb import kwb

    _LOGGER.info('initializing')

    if connection_type == 'serial':
        easyfire = kwb.KWBEasyfire(MODE_SERIAL, "", 0, device)
    elif connection_type == 'tcp':
        easyfire = kwb.KWBEasyfire(MODE_TCP, host, port)
    else:
        return False

    _LOGGER.info('starting thread')
    easyfire.run_thread()
    _LOGGER.info('thread started')

    sensors = []
    for sensor in easyfire.get_sensors():
        if ((sensor.sensor_type != kwb.PROP_SENSOR_RAW)
                or (sensor.sensor_type == kwb.PROP_SENSOR_RAW and raw)):
            sensors.append(KWBSensor(easyfire, sensor, client_name))

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP,
                         lambda event: easyfire.stop_thread())

    add_devices(sensors)


class KWBSensor(Entity):
    """Representation of a KWB Easyfire sensor."""

    def __init__(self, easyfire, sensor, client_name):
        """Initialize the KWB sensor."""
        self._easyfire = easyfire
        self._sensor = sensor
        self._client_name = client_name
        self._name = self._sensor.name

    @property
    def name(self):
        """Return the name."""
        return '{} {}'.format(self._client_name, self._name)

    @property
    def available(self) -> bool:
        """Return if sensor is available."""
        return self._sensor.available

    @property
    def state(self):
        """Return the state of value."""
        if self._sensor.value is not None and self._sensor.available:
            return self._sensor.value
        else:
            return STATE_UNKNOWN

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._sensor.unit_of_measurement
