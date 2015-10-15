"""
homeassistant.components.camera.foscam
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
This component provides basic support for Foscam IP cameras.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.foscam.html
"""
import logging
from homeassistant.helpers import validate_config
from homeassistant.components.camera import DOMAIN
from homeassistant.components.camera import Camera
import requests
import re

_LOGGER = logging.getLogger(__name__)


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """ Adds a Foscam IP Camera. """
    if not validate_config({DOMAIN: config},
                           {DOMAIN: ['username', 'password', 'ip']}, _LOGGER):
        return None

    add_devices_callback([FoscamCamera(config)])


# pylint: disable=too-many-instance-attributes
class FoscamCamera(Camera):
    """ An implementation of a Foscam IP camera. """

    def __init__(self, device_info):
        super(FoscamCamera, self).__init__()

        ip_address = device_info.get('ip')
        port = device_info.get('port', 88)

        self._base_url = 'http://' + ip_address + ':' + str(port) + '/'
        self._username = device_info.get('username')
        self._password = device_info.get('password')
        self._snap_picture_url = self._base_url \
            + 'cgi-bin/CGIProxy.fcgi?cmd=snapPicture&usr=' \
            + self._username + '&pwd=' + self._password
        self._name = device_info.get('name', 'Foscam Camera')

        _LOGGER.info('Using the following URL for %s: %s',
                     self._name, self._snap_picture_url)

    def camera_image(self):
        """ Return a still image reponse from the camera. """

        # send the request to snap a picture
        response = requests.get(self._snap_picture_url)

        # parse the response to find the image file name

        pattern = re.compile('src="[.][.]/(.*[.]jpg)"')
        filename = pattern.search(response.content.decode("utf-8")).group(1)

        # send request for the image
        response = requests.get(self._base_url + filename)

        return response.content

    @property
    def name(self):
        """ Return the name of this device. """
        return self._name
