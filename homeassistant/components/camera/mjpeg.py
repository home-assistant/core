"""
homeassistant.components.camera.mjpeg
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Support for IP Cameras.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.mjpeg/
"""
from contextlib import closing
import logging

import requests
from requests.auth import HTTPBasicAuth

from homeassistant.helpers import validate_config
from homeassistant.components.camera import DOMAIN, Camera

_LOGGER = logging.getLogger(__name__)


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """ Adds a mjpeg IP Camera. """
    if not validate_config({DOMAIN: config}, {DOMAIN: ['mjpeg_url']},
                           _LOGGER):
        return None

    add_devices_callback([MjpegCamera(config)])


# pylint: disable=too-many-instance-attributes
class MjpegCamera(Camera):
    """
    A generic implementation of an IP camera that is reachable over a URL.
    """

    def __init__(self, device_info):
        super().__init__()
        self._name = device_info.get('name', 'Mjpeg Camera')
        self._username = device_info.get('username')
        self._password = device_info.get('password')
        self._mjpeg_url = device_info['mjpeg_url']

    def camera_image(self):
        """ Return a still image response from the camera. """

        def process_response(response):
            """ Take in a response object, return the jpg from it. """
            data = b''
            for chunk in response.iter_content(1024):
                data += chunk
                jpg_start = data.find(b'\xff\xd8')
                jpg_end = data.find(b'\xff\xd9')
                if jpg_start != -1 and jpg_end != -1:
                    jpg = data[jpg_start:jpg_end + 2]
                    return jpg

        if self._username and self._password:
            with closing(requests.get(self._mjpeg_url,
                                      auth=HTTPBasicAuth(self._username,
                                                         self._password),
                                      stream=True)) as response:
                return process_response(response)
        else:
            with closing(requests.get(self._mjpeg_url,
                                      stream=True)) as response:
                return process_response(response)

    @property
    def name(self):
        """ Return the name of this device. """
        return self._name
