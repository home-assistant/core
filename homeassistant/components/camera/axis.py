"""
Support for Axis camera streaming.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.axis/
"""
import logging

from homeassistant.const import (
    CONF_NAME, CONF_USERNAME, CONF_PASSWORD,
    CONF_AUTHENTICATION, HTTP_DIGEST_AUTHENTICATION)
from homeassistant.components.camera.mjpeg import (
    CONF_MJPEG_URL, CONF_STILL_IMAGE_URL, MjpegCamera)

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['axis']
DOMAIN = 'axis'


def _get_image_url(host, mode):
    if mode == 'mjpeg':
        return 'http://{}/axis-cgi/mjpg/video.cgi'.format(host)
    elif mode == 'single':
        return 'http://{}/axis-cgi/jpg/image.cgi'.format(host)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup Axis camera."""
    device_info = {
        CONF_NAME: discovery_info['name'],
        CONF_USERNAME: discovery_info['username'],
        CONF_PASSWORD: discovery_info['password'],
        CONF_MJPEG_URL: _get_image_url(discovery_info['host'], 'mjpeg'),
        CONF_STILL_IMAGE_URL: _get_image_url(discovery_info['host'], 'single'),
        CONF_AUTHENTICATION: HTTP_DIGEST_AUTHENTICATION,
    }
    add_devices([MjpegCamera(hass, device_info)])
