"""
Support for the Netatmo devices.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/netatmo/
"""
import logging
from datetime import timedelta
from urllib.error import HTTPError

import voluptuous as vol

from homeassistant.const import (
    CONF_API_KEY, CONF_PASSWORD, CONF_USERNAME, CONF_DISCOVERY)
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle

REQUIREMENTS = [
    'https://github.com/jabesq/netatmo-api-python/archive/'
    'v0.9.1.zip#lnetatmo==0.9.1']

_LOGGER = logging.getLogger(__name__)

CONF_SECRET_KEY = 'secret_key'

DOMAIN = 'netatmo'

NETATMO_AUTH = None
DEFAULT_DISCOVERY = True

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=10)
MIN_TIME_BETWEEN_EVENT_UPDATES = timedelta(seconds=10)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_SECRET_KEY): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Optional(CONF_DISCOVERY, default=DEFAULT_DISCOVERY): cv.boolean,
    })
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the Netatmo devices."""
    import lnetatmo

    global NETATMO_AUTH
    try:
        NETATMO_AUTH = lnetatmo.ClientAuth(
            config[DOMAIN][CONF_API_KEY], config[DOMAIN][CONF_SECRET_KEY],
            config[DOMAIN][CONF_USERNAME], config[DOMAIN][CONF_PASSWORD],
            'read_station read_camera access_camera '
            'read_thermostat write_thermostat '
            'read_presence access_presence')
    except HTTPError:
        _LOGGER.error("Unable to connect to Netatmo API")
        return False

    if config[DOMAIN][CONF_DISCOVERY]:
        for component in 'camera', 'sensor', 'binary_sensor', 'climate':
            discovery.load_platform(hass, component, DOMAIN, {}, config)

    return True


class CameraData(object):
    """Get the latest data from Netatmo."""

    def __init__(self, auth, home=None):
        """Initialize the data object."""
        self.auth = auth
        self.camera_data = None
        self.camera_names = []
        self.module_names = []
        self.home = home
        self.camera_type = None

    def get_camera_names(self):
        """Return all camera available on the API as a list."""
        self.camera_names = []
        self.update()
        if not self.home:
            for home in self.camera_data.cameras:
                for camera in self.camera_data.cameras[home].values():
                    self.camera_names.append(camera['name'])
        else:
            for camera in self.camera_data.cameras[self.home].values():
                self.camera_names.append(camera['name'])
        return self.camera_names

    def get_module_names(self, camera_name):
        """Return all module available on the API as a list."""
        self.module_names = []
        self.update()
        cam_id = self.camera_data.cameraByName(camera=camera_name,
                                               home=self.home)['id']
        for module in self.camera_data.modules.values():
            if cam_id == module['cam_id']:
                self.module_names.append(module['name'])
        return self.module_names

    def get_camera_type(self, camera=None, home=None, cid=None):
        """Return all module available on the API as a list."""
        for camera_name in self.camera_names:
            self.camera_type = self.camera_data.cameraType(camera_name)
            return self.camera_type

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Call the Netatmo API to update the data."""
        import lnetatmo
        self.camera_data = lnetatmo.CameraData(self.auth, size=100)

    @Throttle(MIN_TIME_BETWEEN_EVENT_UPDATES)
    def update_event(self):
        """Call the Netatmo API to update the events."""
        self.camera_data.updateEvent(
            home=self.home, cameratype=self.camera_type)
