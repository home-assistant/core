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
    ip: 192.168.0.123
    port: 88
    username: visitor
    password: password

camera 2:
    name: 'Second Camera'
    ...
camera 3:
    name: 'Camera Three'
    ...


VARIABLES:

These are the variables for the device_data array:

ip
*Required
The IP address of your foscam device

username
*Required
THe username of a visitor or operator of your camera. Oddly admin accounts don't seem to have access to take snapshots

password
*Required
the password for accessing your camera

name
*Optional
This parameter allows you to override the name of your camera in homeassistant

port
*Optional
The port that the camera is running on. The default is 88.

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
    if not validate_config({DOMAIN: config}, {DOMAIN: ['username', 'password', 'ip']}, _LOGGER):
        return None

    add_devices_callback([FoscamCamera(config)])


# pylint: disable=too-many-instance-attributes
class FoscamCamera(Camera):
    """
    An implementation of a Foscam IP camera.
    """

    def __init__(self, device_info):
        super().__init__()
        self._name = device_info.get('name', 'Foscam Camera')
        self._username = device_info.get('username')
        self._password = device_info.get('password')

        port = device_info.get('port', 88)

        self._base_url = 'http://' + device_info.get('ip') + ':' + str(port) + '/'
        self._snap_picture_url = self._base_url + 'cgi-bin/CGIProxy.fcgi?cmd=snapPicture&usr=' + self._username + '&pwd=' + self._password
        _LOGGER.info('Using the following URL for Foscam camera: ' + self._snap_picture_url)

    def camera_image(self):
        """ Return a still image reponse from the camera """

        # send the request to snap a picture
        response = requests.get(self._snap_picture_url)

        # parse the response to find the image file name
        pattern = re.compile('src="\.\.\/(.*\.jpg)"')
        filename = pattern.search(response.content.decode("utf-8") ).group(1)

        # send request for the image
        response = requests.get(self._base_url + filename)

        return response.content

    @property
    def name(self):
        """ Return the name of this device """
        return self._name
