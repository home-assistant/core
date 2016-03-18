"""
Support for IP Cameras.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.generic/
"""
import logging

import requests
from requests.auth import HTTPBasicAuth

from homeassistant.components.camera import DOMAIN, Camera
from homeassistant.helpers import validate_config

_LOGGER = logging.getLogger(__name__)


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Setup a generic IP Camera."""
    if not validate_config({DOMAIN: config}, {DOMAIN: ['still_image_url']},
                           _LOGGER):
        return None

    add_devices_callback([GenericCamera(config)])


# pylint: disable=too-many-instance-attributes
class GenericCamera(Camera):
    """A generic implementation of an IP camera."""

    def __init__(self, device_info):
        """Initialize a generic camera."""
        super().__init__()
        self._name = device_info.get('name', 'Generic Camera')
        self._username = device_info.get('username')
        self._password = device_info.get('password')
        self._still_image_url = device_info['still_image_url']

    def camera_image(self):
        """Return a still image response from the camera."""
        if self._username and self._password:
            try:
                response = requests.get(
                    self._still_image_url,
                    auth=HTTPBasicAuth(self._username, self._password))
            except requests.exceptions.RequestException as error:
                _LOGGER.error('Error getting camera image: %s', error)
                return None
        else:
            try:
                response = requests.get(self._still_image_url)
            except requests.exceptions.RequestException as error:
                _LOGGER.error('Error getting camera image: %s', error)
                return None

        return response.content

    @property
    def name(self):
        """Return the name of this device."""
        return self._name
