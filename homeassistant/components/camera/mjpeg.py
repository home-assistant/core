"""
Support for IP Cameras.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.mjpeg/
"""
import logging
from contextlib import closing

import requests
from requests.auth import HTTPBasicAuth, HTTPDigestAuth
import voluptuous as vol

from homeassistant.const import (
    CONF_NAME, CONF_USERNAME, CONF_PASSWORD, CONF_AUTHENTICATION,
    HTTP_BASIC_AUTHENTICATION, HTTP_DIGEST_AUTHENTICATION)
from homeassistant.components.camera import (PLATFORM_SCHEMA, Camera)
from homeassistant.helpers import config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_MJPEG_URL = 'mjpeg_url'
CONTENT_TYPE_HEADER = 'Content-Type'

DEFAULT_NAME = 'Mjpeg Camera'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_MJPEG_URL): cv.url,
    vol.Optional(CONF_AUTHENTICATION, default=HTTP_BASIC_AUTHENTICATION):
        vol.In([HTTP_BASIC_AUTHENTICATION, HTTP_DIGEST_AUTHENTICATION]),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_USERNAME): cv.string,
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup a MJPEG IP Camera."""
    add_devices([MjpegCamera(config)])


def extract_image_from_mjpeg(stream):
    """Take in a MJPEG stream object, return the jpg from it."""
    data = b''
    for chunk in stream:
        data += chunk
        jpg_start = data.find(b'\xff\xd8')
        jpg_end = data.find(b'\xff\xd9')
        if jpg_start != -1 and jpg_end != -1:
            jpg = data[jpg_start:jpg_end + 2]
            return jpg


# pylint: disable=too-many-instance-attributes
class MjpegCamera(Camera):
    """An implementation of an IP camera that is reachable over a URL."""

    def __init__(self, device_info):
        """Initialize a MJPEG camera."""
        super().__init__()
        self._name = device_info.get(CONF_NAME)
        self._authentication = device_info.get(CONF_AUTHENTICATION)
        self._username = device_info.get(CONF_USERNAME)
        self._password = device_info.get(CONF_PASSWORD)
        self._mjpeg_url = device_info[CONF_MJPEG_URL]

    def camera_stream(self):
        """Return a MJPEG stream image response directly from the camera."""
        if self._username and self._password:
            if self._authentication == HTTP_DIGEST_AUTHENTICATION:
                auth = HTTPDigestAuth(self._username, self._password)
            else:
                auth = HTTPBasicAuth(self._username, self._password)
            return requests.get(self._mjpeg_url,
                                auth=auth,
                                stream=True, timeout=10)
        else:
            return requests.get(self._mjpeg_url, stream=True, timeout=10)

    def camera_image(self):
        """Return a still image response from the camera."""
        with closing(self.camera_stream()) as response:
            return extract_image_from_mjpeg(response.iter_content(1024))

    def mjpeg_stream(self, response):
        """Generate an HTTP MJPEG stream from the camera."""
        stream = self.camera_stream()
        return response(
            stream.iter_content(chunk_size=1024),
            mimetype=stream.headers[CONTENT_TYPE_HEADER],
            direct_passthrough=True
        )

    @property
    def name(self):
        """Return the name of this camera."""
        return self._name
