"""
Support for the NetAtmo Weather Service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.netatmo/
"""
import logging
import requests

from homeassistant.components.camera import Camera
from homeassistant.loader import get_component

DEPENDENCIES = ["netatmo"]

_LOGGER = logging.getLogger(__name__)


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Setup access to Netatmo Welcome cameras."""
    netatmo = get_component('netatmo')
    data = WelcomeData(netatmo.NETATMO_AUTH)

    for camera_name in data.get_camera_names():
        add_devices_callback([WelcomeCamera(data, camera_name)])


class WelcomeCamera(Camera):
    """Representation of the images published from the Netatmo Welcome camera."""

    def __init__(self, data, camera_name):
        """Setup for access to the BloomSky camera images."""
        super(WelcomeCamera, self).__init__()
        self._data = data
        self._name = camera_name
        self._url = self._data.welcomedata.cameraUrl(camera=camera_name)

    def camera_image(self):
        """Return a still image response from the camera."""
        try:
            response = requests.get('{0}/live/snapshot_720.jpg'.format(self._url))
        except requests.exceptions.RequestException as error:
            _LOGGER.error('Welcome VPN url changed: %s', error)
            self._data.update()
            self._url = self._data.welcomedata.cameraUrl(camera=self._name)
            return None
        return response.content

    @property
    def name(self):
        """Return the name of this BloomSky device."""
        return self._name


class WelcomeData(object):
    """Get the latest data from NetAtmo."""

    def __init__(self, auth):
        """Initialize the data object."""
        self.auth = auth
        self.welcomedata = None
        self.camera_names = []

    def get_camera_names(self):
        """Return all module available on the API as a list."""
        self.update()
        for camera in self.welcomedata.cameras:
            self.camera_names.append(camera['name'])
        return self.camera_names

    def update(self):
        """Call the NetAtmo API to update the data."""
        import lnetatmo
        self.welcomedata = lnetatmo.WelcomeData(self.auth)
