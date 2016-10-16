"""
Support for the Netatmo Welcome camera.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.netatmo/
"""
import logging
from datetime import timedelta

import requests
import voluptuous as vol

from homeassistant.util import Throttle
from homeassistant.components.camera import (Camera, PLATFORM_SCHEMA)
from homeassistant.loader import get_component
from homeassistant.helpers import config_validation as cv

DEPENDENCIES = ['netatmo']

_LOGGER = logging.getLogger(__name__)

CONF_HOME = 'home'
CONF_CAMERAS = 'cameras'

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=10)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_HOME): cv.string,
    vol.Optional(CONF_CAMERAS, default=[]):
        vol.All(cv.ensure_list, [cv.string]),
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup access to Netatmo Welcome cameras."""
    netatmo = get_component('netatmo')
    home = config.get(CONF_HOME)
    import lnetatmo
    try:
        data = WelcomeData(netatmo.NETATMO_AUTH, home)
    except lnetatmo.NoDevice:
        return None

    for camera_name in data.get_camera_names():
        if config[CONF_CAMERAS] != []:
            if camera_name not in config[CONF_CAMERAS]:
                continue
        add_devices([WelcomeCamera(data, camera_name, home)])


class WelcomeCamera(Camera):
    """Representation of the images published from Welcome camera."""

    def __init__(self, data, camera_name, home):
        """Setup for access to the Netatmo camera images."""
        super(WelcomeCamera, self).__init__()
        self._data = data
        self._camera_name = camera_name
        if home:
            self._name = home + ' / ' + camera_name
        else:
            self._name = camera_name
        self._vpnurl, self._localurl = self._data.welcomedata.cameraUrls(
            camera=camera_name
            )

    def camera_image(self):
        """Return a still image response from the camera."""
        try:
            if self._localurl:
                response = requests.get('{0}/live/snapshot_720.jpg'.format(
                    self._localurl), timeout=10)
            else:
                response = requests.get('{0}/live/snapshot_720.jpg'.format(
                    self._vpnurl), timeout=10)
        except requests.exceptions.RequestException as error:
            _LOGGER.error('Welcome VPN url changed: %s', error)
            self._data.update()
            (self._vpnurl, self._localurl) = \
                self._data.welcomedata.cameraUrls(camera=self._camera_name)
            return None
        return response.content

    @property
    def name(self):
        """Return the name of this Netatmo Welcome device."""
        return self._name


class WelcomeData(object):
    """Get the latest data from NetAtmo."""

    def __init__(self, auth, home=None):
        """Initialize the data object."""
        self.auth = auth
        self.welcomedata = None
        self.camera_names = []
        self.home = home

    def get_camera_names(self):
        """Return all module available on the API as a list."""
        self.update()
        if not self.home:
            for home in self.welcomedata.cameras:
                for camera in self.welcomedata.cameras[home].values():
                    self.camera_names.append(camera['name'])
        else:
            for camera in self.welcomedata.cameras[self.home].values():
                self.camera_names.append(camera['name'])
        return self.camera_names

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Call the NetAtmo API to update the data."""
        import lnetatmo
        self.welcomedata = lnetatmo.WelcomeData(self.auth)
