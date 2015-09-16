"""
Support for Foscam IP Cameras.

This component provides basic support for Foscam IP cameras. 

As part of the basic support the following features will be provided:
-MJPEG video streaming
-Saving a snapshot
-Recording(JPEG frame capture)

To use this component, add the following to your config/configuration.yaml:

camera:
    platform: foscam
    name: Door Camera
    username: visitor (a user with visitor/operator privilege is required, admin accounts oddly do not seem to work)
    password: <password>
    ip: <camera ip address>

"""
import logging
from requests.auth import HTTPBasicAuth
from homeassistant.helpers import validate_config
from homeassistant.components.camera import DOMAIN
from homeassistant.components.camera import Camera
import requests
import re

_LOGGER = logging.getLogger(__name__)


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """ Adds a generic IP Camera. """
    if not validate_config({DOMAIN: config}, {DOMAIN: ['username', 'password', 'ip']},
                           _LOGGER):
        return None

    add_devices_callback([FoscamCamera(config)])


# pylint: disable=too-many-instance-attributes
class FoscamCamera(Camera):
    """
    A generic implementation of an IP camera that is reachable over a URL.
    """

    def __init__(self, device_info):
        super().__init__()
        self._name = device_info.get('name', 'Foscam Camera')
        self._username = device_info.get('username')
        self._password = device_info.get('password')
        self._base_url = 'http://' + device_info.get('ip') + ':88/'
        self._snap_picture_url = self._base_url + 'cgi-bin/CGIProxy.fcgi?cmd=snapPicture&usr=' + self._username + '&pwd=' + self._password

    def camera_image(self):
        """ Return a still image reponse from the camera """

        response = requests.get(self._snap_picture_url)
        pattern = re.compile('src="\.\.\/(.*\.jpg)"')
        filename = pattern.search(response.content.decode("utf-8") ).group(1)

        response = requests.get(self._base_url + filename)

        return response.content

    @property
    def name(self):
        """ Return the name of this device """
        return self._name
