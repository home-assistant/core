"""Support for Axis camera streaming."""

from homeassistant.components.mjpeg.camera import (
    CONF_MJPEG_URL, CONF_STILL_IMAGE_URL, MjpegCamera, filter_urllib3_logging)
from homeassistant.const import (
    CONF_AUTHENTICATION, CONF_DEVICE, CONF_HOST, CONF_MAC, CONF_NAME,
    CONF_PASSWORD, CONF_PORT, CONF_USERNAME, HTTP_DIGEST_AUTHENTICATION)
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN as AXIS_DOMAIN

DEPENDENCIES = [AXIS_DOMAIN]

AXIS_IMAGE = 'http://{}:{}/axis-cgi/jpg/image.cgi'
AXIS_VIDEO = 'http://{}:{}/axis-cgi/mjpg/video.cgi'


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Axis camera video stream."""
    filter_urllib3_logging()

    serial_number = config_entry.data[CONF_MAC]
    device = hass.data[AXIS_DOMAIN][serial_number]

    config = {
        CONF_NAME: config_entry.data[CONF_NAME],
        CONF_USERNAME: config_entry.data[CONF_DEVICE][CONF_USERNAME],
        CONF_PASSWORD: config_entry.data[CONF_DEVICE][CONF_PASSWORD],
        CONF_MJPEG_URL: AXIS_VIDEO.format(
            config_entry.data[CONF_DEVICE][CONF_HOST],
            config_entry.data[CONF_DEVICE][CONF_PORT]),
        CONF_STILL_IMAGE_URL: AXIS_IMAGE.format(
            config_entry.data[CONF_DEVICE][CONF_HOST],
            config_entry.data[CONF_DEVICE][CONF_PORT]),
        CONF_AUTHENTICATION: HTTP_DIGEST_AUTHENTICATION,
    }
    async_add_entities([AxisCamera(config, device)])


class AxisCamera(MjpegCamera):
    """Representation of a Axis camera."""

    def __init__(self, config, device):
        """Initialize Axis Communications camera component."""
        super().__init__(config)
        self.device_config = config
        self.device = device
        self.port = device.config_entry.data[CONF_DEVICE][CONF_PORT]
        self.unsub_dispatcher = None

    async def async_added_to_hass(self):
        """Subscribe camera events."""
        self.unsub_dispatcher = async_dispatcher_connect(
            self.hass, 'axis_{}_new_ip'.format(self.device.name), self._new_ip)

    def _new_ip(self, host):
        """Set new IP for video stream."""
        self._mjpeg_url = AXIS_VIDEO.format(host, self.port)
        self._still_image_url = AXIS_IMAGE.format(host, self.port)

    @property
    def unique_id(self):
        """Return a unique identifier for this device."""
        return '{}-camera'.format(self.device.serial)

    @property
    def device_info(self):
        """Return a device description for device registry."""
        return {
            'identifiers': {(AXIS_DOMAIN, self.device.serial)}
        }
