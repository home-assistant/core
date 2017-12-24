"""
Support for the (unofficial) Tado api.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/tado/
"""
import logging
import urllib
from datetime import timedelta

import voluptuous as vol

from homeassistant.helpers.discovery import load_platform
from homeassistant.helpers import config_validation as cv
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.util import Throttle

REQUIREMENTS = ['python-tado==0.2.2']

_LOGGER = logging.getLogger(__name__)

DATA_TADO = 'tado_data'
DOMAIN = 'tado'

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=10)

TADO_COMPONENTS = [
    'sensor', 'climate'
]

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string
    })
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up of the Tado component."""
    username = config[DOMAIN][CONF_USERNAME]
    password = config[DOMAIN][CONF_PASSWORD]

    from PyTado.interface import Tado

    try:
        tado = Tado(username, password)
        tado.setDebugging(True)
    except (RuntimeError, urllib.error.HTTPError):
        _LOGGER.error("Unable to connect to mytado with username and password")
        return False

    hass.data[DATA_TADO] = TadoDataStore(tado)

    for component in TADO_COMPONENTS:
        load_platform(hass, component, DOMAIN, {}, config)

    return True


class TadoDataStore:
    """An object to store the Tado data."""

    def __init__(self, tado):
        """Initialize Tado data store."""
        self.tado = tado

        self.sensors = {}
        self.data = {}

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Update the internal data from mytado.com."""
        for data_id, sensor in list(self.sensors.items()):
            data = None

            try:
                if 'zone' in sensor:
                    _LOGGER.info("Querying mytado.com for zone %s %s",
                                 sensor['id'], sensor['name'])
                    data = self.tado.getState(sensor['id'])

                if 'device' in sensor:
                    _LOGGER.info("Querying mytado.com for device %s %s",
                                 sensor['id'], sensor['name'])
                    data = self.tado.getDevices()[0]

            except RuntimeError:
                _LOGGER.error("Unable to connect to myTado. %s %s",
                              sensor['id'], sensor['id'])

            self.data[data_id] = data

    def add_sensor(self, data_id, sensor):
        """Add a sensor to update in _update()."""
        self.sensors[data_id] = sensor
        self.data[data_id] = None

    def get_data(self, data_id):
        """Get the cached data."""
        data = {'error': 'no data'}

        if data_id in self.data:
            data = self.data[data_id]

        return data

    def get_zones(self):
        """Wrap for getZones()."""
        return self.tado.getZones()

    def get_capabilities(self, tado_id):
        """Wrap for getCapabilities(..)."""
        return self.tado.getCapabilities(tado_id)

    def get_me(self):
        """Wrap for getMet()."""
        return self.tado.getMe()

    def reset_zone_overlay(self, zone_id):
        """Wrap for resetZoneOverlay(..)."""
        self.tado.resetZoneOverlay(zone_id)
        self.update(no_throttle=True)  # pylint: disable=unexpected-keyword-arg

    def set_zone_overlay(self, zone_id, mode, temperature=None, duration=None):
        """Wrap for setZoneOverlay(..)."""
        self.tado.setZoneOverlay(zone_id, mode, temperature, duration)
        self.update(no_throttle=True)  # pylint: disable=unexpected-keyword-arg
