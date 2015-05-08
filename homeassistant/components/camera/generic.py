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

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """ Find and return Vera lights. """
    if not validate_config({DOMAIN: config},
                       {DOMAIN: ['base_url', CONF_USERNAME, CONF_PASSWORD]},
                       _LOGGER):
        return None

    camera = Camera(hass, config)
    cameras = [camera]

    add_devices_callback(cameras)

