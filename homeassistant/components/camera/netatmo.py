"""
Support for the Netatmo Welcome camera.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.netatmo/
"""
import logging

import requests
import voluptuous as vol

from homeassistant.components.netatmo import WelcomeData
from homeassistant.components.camera import (Camera, PLATFORM_SCHEMA)
from homeassistant.loader import get_component
from homeassistant.helpers import config_validation as cv

DEPENDENCIES = ['netatmo']

_LOGGER = logging.getLogger(__name__)

CONF_HOME = 'home'
CONF_CAMERAS = 'cameras'

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
        for camera_name in data.get_camera_names():
            if CONF_CAMERAS in config:
                if config[CONF_CAMERAS] != [] and \
                   camera_name not in config[CONF_CAMERAS]:
                    continue
            add_devices([WelcomeCamera(data, camera_name, home)])
    except lnetatmo.NoDevice:
        return None


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
        camera_id = data.welcomedata.cameraByName(camera=camera_name,
                                                  home=home)['id']
        self._unique_id = "Welcome_camera {0} - {1}".format(self._name,
                                                            camera_id)
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

    @property
    def unique_id(self):
        """Return the unique ID for this sensor."""
        return self._unique_id
