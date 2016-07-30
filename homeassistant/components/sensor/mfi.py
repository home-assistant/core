"""
Support for Ubiquiti mFi sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.mfi/
"""
import logging

import requests

from homeassistant.components.sensor import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, TEMP_CELSIUS
from homeassistant.helpers import validate_config
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['mficlient==0.3.0']

_LOGGER = logging.getLogger(__name__)

STATE_ON = 'on'
STATE_OFF = 'off'
DIGITS = {
    'volts': 1,
    'amps': 1,
    'active_power': 0,
    'temperature': 1,
}
SENSOR_MODELS = [
    'Ubiquiti mFi-THS',
    'Ubiquiti mFi-CS',
    'Outlet',
    'Input Analog',
    'Input Digital',
]
CONF_TLS = 'use_tls'
CONF_VERIFY_TLS = 'verify_tls'


# pylint: disable=unused-variable
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup mFi sensors."""
    if not validate_config({DOMAIN: config},
                           {DOMAIN: ['host',
                                     CONF_USERNAME,
                                     CONF_PASSWORD]},
                           _LOGGER):
        _LOGGER.error('A host, username, and password are required')
        return False

    host = config.get('host')
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    use_tls = bool(config.get(CONF_TLS, True))
    verify_tls = bool(config.get(CONF_VERIFY_TLS, True))
    default_port = use_tls and 6443 or 6080
    port = int(config.get('port', default_port))

    from mficlient.client import FailedToLogin, MFiClient

    try:
        client = MFiClient(host, username, password, port=port,
                           use_tls=use_tls, verify=verify_tls)
    except (FailedToLogin, requests.exceptions.ConnectionError) as ex:
        _LOGGER.error('Unable to connect to mFi: %s', str(ex))
        return False

    add_devices(MfiSensor(port, hass)
                for device in client.get_devices()
                for port in device.ports.values()
                if port.model in SENSOR_MODELS)


class MfiSensor(Entity):
    """Representation of a mFi sensor."""

    def __init__(self, port, hass):
        """Initialize the sensor."""
        self._port = port
        self._hass = hass

    @property
    def name(self):
        """Return the name of th sensor."""
        return self._port.label

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._port.model == 'Input Digital':
            return self._port.value > 0 and STATE_ON or STATE_OFF
        else:
            digits = DIGITS.get(self._port.tag, 0)
            return round(self._port.value, digits)

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        if self._port.tag == 'temperature':
            return TEMP_CELSIUS
        elif self._port.tag == 'active_pwr':
            return 'Watts'
        elif self._port.model == 'Input Digital':
            return 'State'
        return self._port.tag

    def update(self):
        """Get the latest data."""
        self._port.refresh()
