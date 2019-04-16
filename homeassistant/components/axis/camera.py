"""Support for Axis camera streaming."""

from homeassistant.components.camera import SUPPORT_STREAM
from homeassistant.components.mjpeg.camera import (
    CONF_MJPEG_URL, CONF_STILL_IMAGE_URL, MjpegCamera, filter_urllib3_logging)
from homeassistant.const import (
    CONF_AUTHENTICATION, CONF_DEVICE, CONF_HOST, CONF_MAC, CONF_NAME,
    CONF_PASSWORD, CONF_PORT, CONF_USERNAME, HTTP_DIGEST_AUTHENTICATION)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN as AXIS_DOMAIN

AXIS_IMAGE = 'http://{}:{}/axis-cgi/jpg/image.cgi'
AXIS_VIDEO = 'http://{}:{}/axis-cgi/mjpg/video.cgi'
AXIS_STREAM = 'rtsp://{}:{}@{}/axis-media/media.amp?videocodec=h264'


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
        self.unsub_dispatcher = []

    async def async_added_to_hass(self):
        """Subscribe camera events."""
        self.unsub_dispatcher.append(async_dispatcher_connect(
            self.hass, self.device.event_new_address, self._new_address))
        self.unsub_dispatcher.append(async_dispatcher_connect(
            self.hass, self.device.event_reachable, self.update_callback))

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect device object when removed."""
        for unsub_dispatcher in self.unsub_dispatcher:
            unsub_dispatcher()

    @property
    def supported_features(self):
        """Return supported features."""
        return SUPPORT_STREAM

    @property
    def stream_source(self):
        """Return the stream source."""
        return AXIS_STREAM.format(
            self.device.config_entry.data[CONF_DEVICE][CONF_USERNAME],
            self.device.config_entry.data[CONF_DEVICE][CONF_PASSWORD],
            self.device.host)

    @callback
    def update_callback(self, no_delay=None):
        """Update the cameras state."""
        self.async_schedule_update_ha_state()

    @property
    def available(self):
        """Return True if device is available."""
        return self.device.available

    def _new_address(self):
        """Set new device address for video stream."""
        self._mjpeg_url = AXIS_VIDEO.format(self.device.host, self.port)
        self._still_image_url = AXIS_IMAGE.format(self.device.host, self.port)

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
