"""
Support for IP Cameras.

This component provides basic support for IP cameras. For the basic support to
work you camera must support accessing a JPEG snapshot via a URL and you will
need to specify the "still_image_url" parameter which should be the location of
the JPEG image.

As part of the basic support the following features will be provided:
-MJPEG video streaming
-Saving a snapshot
-Recording(JPEG frame capture)

To use this component, add the following to your config/configuration.yaml:

camera:
    platform: generic
    name: Door Camera
    username: YOUR_USERNAME
    password: YOUR_PASSWORD
    still_image_url: http://YOUR_CAMERA_IP_AND_PORT/image.jpg


VARIABLES:

These are the variables for the device_data array:

still_image_url
*Required
The URL your camera serves the image on.
Example: http://192.168.1.21:2112/

name
*Optional
This parameter allows you to override the name of your camera in homeassistant

username
*Optional
THe username for acessing your camera

password
*Optional
the password for accessing your camera


"""
import logging
from requests.auth import HTTPBasicAuth
from homeassistant.helpers import validate_config
from homeassistant.components.camera import DOMAIN
from homeassistant.components.camera import Camera
import requests

_LOGGER = logging.getLogger(__name__)


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """ Adds a generic IP Camera. """
    if not validate_config({DOMAIN: config}, {DOMAIN: ['still_image_url']},
                           _LOGGER):
        return None

    add_devices_callback([GenericCamera(config)])


# pylint: disable=too-many-instance-attributes
class GenericCamera(Camera):
    """
    A generic implementation of an IP camera that is reachable over a URL.
    """

    def __init__(self, device_info):
        super().__init__()
        self._name = device_info.get('name', 'Generic Camera')
        self._username = device_info.get('username')
        self._password = device_info.get('password')
        self._still_image_url = device_info['still_image_url']

    def camera_image(self):
        """ Return a still image reponse from the camera """
        if self._username and self._password:
            response = requests.get(
                self._still_image_url,
                auth=HTTPBasicAuth(self._username, self._password))
        else:
            response = requests.get(self._still_image_url)

        return response.content

    @property
    def name(self):
        """ Return the name of this device """
        return self._name
