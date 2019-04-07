"""Support for the Netatmo cameras."""
import logging

import requests
import voluptuous as vol

from homeassistant.components.camera import PLATFORM_SCHEMA, Camera
from homeassistant.const import CONF_VERIFY_SSL
from homeassistant.helpers import config_validation as cv

from . import CameraData

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


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up access to Netatmo cameras."""
    netatmo = hass.components.netatmo
    home = config.get(CONF_HOME)
    verify_ssl = config.get(CONF_VERIFY_SSL, True)
    import pyatmo
    try:
        data = CameraData(hass, netatmo.NETATMO_AUTH, home)
        for camera_name in data.get_camera_names():
            camera_type = data.get_camera_type(camera=camera_name, home=home)
            if CONF_CAMERAS in config:
                if config[CONF_CAMERAS] != [] and \
                   camera_name not in config[CONF_CAMERAS]:
                    continue
            add_entities([NetatmoCamera(data, camera_name, home,
                                        camera_type, verify_ssl)])
        data.get_persons()
    except pyatmo.NoDevice:
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
        if self._cameratype == "NACamera":
            return "Welcome"
        return None
