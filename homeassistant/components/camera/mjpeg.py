"""
homeassistant.components.camera.mjpeg
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Support for IP Cameras.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.mjpeg.html
"""
import logging
from requests.auth import HTTPBasicAuth
from homeassistant.helpers import validate_config
from homeassistant.components.camera import DOMAIN
from homeassistant.components.camera import Camera
import urllib.request

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
        """ Return a still image reponse from the camera. """
        if self._username and self._password:
            password_mgr = urllib.request.HTTPPasswordMgrWithDefaultRealm()
            password_mgr.add_password(None, self._mjpeg_url, self._username, self._password)
            handler = urllib.request.HTTPBasicAuthHandler(password_mgr)
            opener = urllib.request.build_opener(handler)
            urllib.request.install_opener(opener)

        stream=urllib.request.urlopen(self._mjpeg_url)
        charset = stream.headers.get_param('charset')
        bytes = b''
        while True:
            bytes += stream.read(1024)
            a = bytes.find(b'\xff\xd8')
            b = bytes.find(b'\xff\xd9')
            if a != -1 and b != -1:
                jpg = bytes[a:b+2]
                return jpg

    @property
    def name(self):
        """ Return the name of this device. """
        return self._name
