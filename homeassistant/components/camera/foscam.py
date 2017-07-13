"""
This component provides basic support for Foscam IP cameras.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.foscam/
"""
import logging

import requests
import voluptuous as vol

from homeassistant.components.camera import (Camera, PLATFORM_SCHEMA)
from homeassistant.const import (
    CONF_NAME, CONF_USERNAME, CONF_PASSWORD, CONF_PORT)
from homeassistant.helpers import config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_IP = 'ip'

CAMERA_ARMED = "armed"
CAMERA_DISARMED = "disarmed"

DEFAULT_NAME = 'Foscam Camera'
DEFAULT_PORT = 88

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_IP): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up a Foscam IP Camera."""
    add_devices([FoscamCamera(config)])


class FoscamCamera(Camera):
    """An implementation of a Foscam IP camera."""

    def __init__(self, device_info):
        """Initialize a Foscam camera."""
        super(FoscamCamera, self).__init__()

        ip_address = device_info.get(CONF_IP)
        port = device_info.get(CONF_PORT)

        self._base_url = 'http://{}:{}/'.format(ip_address, port)

        uri_template = self._base_url \
            + 'cgi-bin/CGIProxy.fcgi?' \
            + 'cmd=snapPicture2&usr={}&pwd={}'

        self._username = device_info.get(CONF_USERNAME)
        self._password = device_info.get(CONF_PASSWORD)
        self._snap_picture_url = uri_template.format(
            self._username,
            self._password
        )
        self._name = device_info.get(CONF_NAME)
        self._motion_status = False

        _LOGGER.info("Using the following URL for %s: %s",
                     self._name, uri_template.format('***', '***'))

    def camera_image(self):
        """Return a still image reponse from the camera."""
        # Send the request to snap a picture and return raw jpg data
        # Handle exception if host is not reachable or url failed
        try:
            response = requests.get(self._snap_picture_url, timeout=10)
        except requests.exceptions.ConnectionError:
            return None
        else:
            return response.content

    @property
    def name(self):
        """Return the name of this camera."""
        return self._name

    def set_motion_status(self, mode):
        """Post to the camera and enable motion detection."""
        if mode == CAMERA_ARMED:
            enabled = '1'
        else:
            enabled = '0'

        # Fill the URI with the command to enable motion detection
        # Along with that as per foscam spec we have to set
        # sensitivity: how much sensitivity camera should detect
        # trigger interval: interval between each motion triggers
        # schedule: set schedule for days. default is 24x7
        # area: sort of like zones. default is all areas visible to cam
        uri_template = self._base_url \
            + 'cgi-bin/CGIProxy.fcgi?' \
            + 'cmd=setMotionDetectConfig' \
            + '&Enable={}&usr={}&pwd={}' \
            + '&linkage=0&snapInterval=3' \
            + '&sensitivity=2&triggerInterval=0' \
            + '&schedule0=281474976710655' \
            + '&schedule1=281474976710655' \
            + '&schedule2=281474976710655' \
            + '&schedule3=281474976710655' \
            + '&schedule4=281474976710655' \
            + '&schedule5=281474976710655' \
            + '&schedule6=281474976710655' \
            + '&area0=1024&area1=1023' \
            + '&area2=1024&area3=1023' \
            + '&area4=1024&area5=1023' \
            + '&area6=1024&area7=1023' \
            + '&area8=1024&area9=1023'
            
        self._set_motion_status_url = uri_template.format(
            enabled,
            self._username,
            self._password
        )

        try:
            response = requests.get(self._set_motion_status_url, timeout=10)
        except requests.exceptions.ConnectionError:
            return None
        else:
            return response.content

    @property
    def motion_detection_enabled(self):
        """Is motion detection enabled or disabled."""
        return self._motion_status

    def enable_motion_detection(self):
        """Enable motion detection in camera."""
        self._motion_status = True
        self.set_motion_status(CAMERA_ARMED)

    def disable_motion_detection(self):
        """Disable motion detection in camera."""
        self._motion_status = False
        self.set_motion_status(CAMERA_DISARMED)
