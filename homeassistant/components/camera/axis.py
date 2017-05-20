"""
Support for Axis camera streaming.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.axis/
"""
import logging

from homeassistant.const import (
    CONF_HOST, CONF_NAME, CONF_USERNAME, CONF_PASSWORD,
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
    config = {
        CONF_NAME: discovery_info[CONF_NAME],
        CONF_USERNAME: discovery_info[CONF_USERNAME],
        CONF_PASSWORD: discovery_info[CONF_PASSWORD],
        CONF_MJPEG_URL: _get_image_url(discovery_info[CONF_HOST], 'mjpeg'),
        CONF_STILL_IMAGE_URL: _get_image_url(discovery_info[CONF_HOST],
                                             'single'),
        CONF_AUTHENTICATION: HTTP_DIGEST_AUTHENTICATION,
    }
    add_devices([AxisCamera(hass, config)])


class AxisCamera(MjpegCamera):
    """Bla"""
    def __init__(self, hass, config):
        """Initialize Axis Communications camera component."""
        super().__init__(hass, config)
        hass.bus.listen(DOMAIN + '_' + config[CONF_NAME], self.new_ip)

    def new_ip(self, event):
        """Set new IP for video stream"""
        self._mjpeg_url = _get_image_url(event.data.get(CONF_HOST), 'mjpeg')
        self._still_image_url = _get_image_url(event.data.get(CONF_HOST),
                                               'mjpeg')
