"""
Support for IP Cameras.

This component provides basic support for IP camera models that do not have
a speicifc HA component.

As part of the basic support the following features will be provided:
-MJPEG video streaming
-Saving a snapshot
-Recording(JPEG frame capture)

NOTE: for the basic support to work you camera must support accessing a JPEG
snapshot via a URL and you will need to specify the "still_image_url" parameter
which should be the location of the JPEG snapshot relative to you specified
base_url.  For example "snapshot.cgi" or "image.jpg".

To use this component you will need to add something like the following to your
config/configuration.yaml

camera:
    platform: generic
    base_url: http://YOUR_CAMERA_IP_AND_PORT/
    name: Door Camera
    brand: dlink
    family: DCS
    model: DCS-930L
    username: YOUR_USERNAME
    password: YOUR_PASSWORD
    still_image_url: image.jpg


VARIABLES:

These are the variables for the device_data array:

base_url
*Required
The base URL for accessing you camera
Example: http://192.168.1.21:2112/

name
*Optional
This parameter allows you to override the name of your camera in homeassistant


brand
*Optional
The manufacturer of your device, used to help load the specific camera
functionality.

family
*Optional
The family of devices by the specified brand, useful when many models
support the same settings.  This used when attempting load up specific
device functionality.

model
*Optional
The specific model number of your device.

still_image_url
*Optional
Useful if using an unsupported camera model.  This should point to the location
of the still image on your particular camera and should be relative to your
specified base_url.
Example: cam/image.jpg

username
*Required
THe username for acessing your camera

password
*Required
the password for accessing your camera


"""
import logging
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers import validate_config
from homeassistant.components.camera import DOMAIN
from homeassistant.components.camera import Camera
import requests

_LOGGER = logging.getLogger(__name__)


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """ Find and return Vera lights. """
    if not validate_config(
            {DOMAIN: config},
            {DOMAIN: ['base_url', CONF_USERNAME, CONF_PASSWORD]},
            _LOGGER):
        return None

    camera = GenericCamera(hass, config)
    cameras = [camera]

    add_devices_callback(cameras)


# pylint: disable=too-many-instance-attributes
class GenericCamera(Camera):
    """
    Base class for cameras.
    This is quite a large class but the camera component encompasses a lot of
    functionality.  It should take care of most of the heavy lifting and
    plumbing associated with adding support for additional models of camera.
    If you are adding support for a new camera your entity class should inherit
    from this.
    """

    def __init__(self, hass, device_info):
        self.hass = hass
        self._device_info = device_info
        self._base_url = device_info.get('base_url')
        if not self._base_url.endswith('/'):
            self._base_url = self._base_url + '/'
        self._username = device_info.get('username')
        self._password = device_info.get('password')
        self._is_streaming = False
        self._still_image_url = device_info.get('still_image_url', 'image.jpg')
        self._logger = logging.getLogger(__name__)

    def get_camera_image(self):
        """ Return a still image reponse from the camera """
        response = requests.get(
            self.still_image_url,
            auth=(self._username, self._password))

        return response.content

    @property
    def device_info(self):
        """ Return the config data for this device """
        return self._device_info

    @property
    def name(self):
        """ Return the name of this device """
        return self._device_info.get('name') or super().name

    @property
    def state_attributes(self):
        """ Returns optional state attributes. """
        attr = super().state_attributes

        return attr

    @property
    def base_url(self):
        return self._base_url

    @property
    def username(self):
        return self._username

    @property
    def password(self):
        return self._password

    @property
    def is_streaming(self):
        return self._is_streaming

    @is_streaming.setter
    # pylint: disable=arguments-differ
    def is_streaming(self, value):
        self._is_streaming = value

    @property
    def still_image_url(self):
        """ This should be implemented by different camera models. """
        return self.base_url + self._still_image_url
