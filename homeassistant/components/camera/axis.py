"""
Support for Axis camera streaming.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.axis/
"""
import logging

from homeassistant.components.camera.mjpeg import (
    CONF_MJPEG_URL, CONF_STILL_IMAGE_URL, MjpegCamera)
from homeassistant.const import (
    CONF_AUTHENTICATION, CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_PORT,
    CONF_USERNAME, HTTP_DIGEST_AUTHENTICATION)
from homeassistant.helpers.dispatcher import dispatcher_connect

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'axis'
DEPENDENCIES = [DOMAIN]


def _get_image_url(host, port, mode):
    """Set the URL to get the image."""
    if mode == 'mjpeg':
        return 'http://{}:{}/axis-cgi/mjpg/video.cgi'.format(host, port)
    if mode == 'single':
        return 'http://{}:{}/axis-cgi/jpg/image.cgi'.format(host, port)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Axis camera."""
    camera_config = {
        CONF_NAME: discovery_info[CONF_NAME],
        CONF_USERNAME: discovery_info[CONF_USERNAME],
        CONF_PASSWORD: discovery_info[CONF_PASSWORD],
        CONF_MJPEG_URL: _get_image_url(
            discovery_info[CONF_HOST], str(discovery_info[CONF_PORT]),
            'mjpeg'),
        CONF_STILL_IMAGE_URL: _get_image_url(
            discovery_info[CONF_HOST], str(discovery_info[CONF_PORT]),
            'single'),
        CONF_AUTHENTICATION: HTTP_DIGEST_AUTHENTICATION,
    }
    add_entities([AxisCamera(
        hass, camera_config, str(discovery_info[CONF_PORT]))])


class AxisCamera(MjpegCamera):
    """Representation of a Axis camera."""

    def __init__(self, hass, config, port):
        """Initialize Axis Communications camera component."""
        super().__init__(config)
        self.port = port
        dispatcher_connect(
            hass, DOMAIN + '_' + config[CONF_NAME] + '_new_ip', self._new_ip)

    def _new_ip(self, host):
        """Set new IP for video stream."""
        self._mjpeg_url = _get_image_url(host, self.port, 'mjpeg')
        self._still_image_url = _get_image_url(host, self.port, 'single')
