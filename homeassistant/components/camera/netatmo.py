"""
Support for the Netatmo cameras.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.netatmo/.
"""
import logging

import requests
import voluptuous as vol

from homeassistant.const import CONF_VERIFY_SSL
from homeassistant.components.netatmo import CameraData
from homeassistant.components.camera import (Camera, PLATFORM_SCHEMA)
from homeassistant.loader import get_component
from homeassistant.helpers import config_validation as cv

DEPENDENCIES = ['netatmo']

_LOGGER = logging.getLogger(__name__)

CONF_HOME = 'home'
CONF_CAMERAS = 'cameras'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_VERIFY_SSL, default=True): cv.boolean,
    vol.Optional(CONF_HOME): cv.string,
    vol.Optional(CONF_CAMERAS, default=[]):
        vol.All(cv.ensure_list, [cv.string]),
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up access to Netatmo cameras."""
    netatmo = get_component('netatmo')
    home = config.get(CONF_HOME)
    verify_ssl = config.get(CONF_VERIFY_SSL, True)
    import lnetatmo
    try:
        data = CameraData(netatmo.NETATMO_AUTH, home)
        for camera_name in data.get_camera_names():
            camera_type = data.get_camera_type(camera=camera_name, home=home)
            if CONF_CAMERAS in config:
                if config[CONF_CAMERAS] != [] and \
                   camera_name not in config[CONF_CAMERAS]:
                    continue
            add_devices([NetatmoCamera(data, camera_name, home,
                                       camera_type, verify_ssl)])
    except lnetatmo.NoDevice:
        return None


class NetatmoCamera(Camera):
    """Representation of the images published from a Netatmo camera."""

    def __init__(self, data, camera_name, home, camera_type, verify_ssl):
        """Set up for access to the Netatmo camera images."""
        super(NetatmoCamera, self).__init__()
        self._data = data
        self._camera_name = camera_name
        self._verify_ssl = verify_ssl
        if home:
            self._name = home + ' / ' + camera_name
        else:
            self._name = camera_name
        camera_id = data.camera_data.cameraByName(
            camera=camera_name, home=home)['id']
        self._unique_id = "Welcome_camera {0} - {1}".format(
            self._name, camera_id)
        self._vpnurl, self._localurl = self._data.camera_data.cameraUrls(
            camera=camera_name
            )
        self._cameratype = camera_type

    def camera_image(self):
        """Return a still image response from the camera."""
        try:
            if self._localurl:
                response = requests.get('{0}/live/snapshot_720.jpg'.format(
                    self._localurl), timeout=10)
            elif self._vpnurl:
                response = requests.get('{0}/live/snapshot_720.jpg'.format(
                    self._vpnurl), timeout=10, verify=self._verify_ssl)
            else:
                _LOGGER.error("Welcome VPN URL is None")
                self._data.update()
                (self._vpnurl, self._localurl) = \
                    self._data.camera_data.cameraUrls(camera=self._camera_name)
                return None
        except requests.exceptions.RequestException as error:
            _LOGGER.error("Welcome URL changed: %s", error)
            self._data.update()
            (self._vpnurl, self._localurl) = \
                self._data.camera_data.cameraUrls(camera=self._camera_name)
            return None
        return response.content

    @property
    def name(self):
        """Return the name of this Netatmo camera device."""
        return self._name

    @property
    def brand(self):
        """Return the camera brand."""
        return "Netatmo"

    @property
    def model(self):
        """Return the camera model."""
        if self._cameratype == "NOC":
            return "Presence"
        elif self._cameratype == "NACamera":
            return "Welcome"
        else:
            return None

    @property
    def unique_id(self):
        """Return the unique ID for this sensor."""
        return self._unique_id
