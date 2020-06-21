"""Support for Axis camera streaming."""

from homeassistant.components.camera import SUPPORT_STREAM
from homeassistant.components.mjpeg.camera import (
    CONF_MJPEG_URL,
    CONF_STILL_IMAGE_URL,
    MjpegCamera,
    filter_urllib3_logging,
)
from homeassistant.const import (
    CONF_AUTHENTICATION,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    HTTP_DIGEST_AUTHENTICATION,
)
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .axis_base import AxisEntityBase
from .const import DEFAULT_STREAM_PROFILE, DOMAIN as AXIS_DOMAIN


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Axis camera video stream."""
    filter_urllib3_logging()

    device = hass.data[AXIS_DOMAIN][config_entry.unique_id]

    if not device.api.vapix.params.image_format:
        return

    async_add_entities([AxisCamera(device)])


class AxisCamera(AxisEntityBase, MjpegCamera):
    """Representation of a Axis camera."""

    def __init__(self, device):
        """Initialize Axis Communications camera component."""
        AxisEntityBase.__init__(self, device)

        config = {
            CONF_NAME: device.config_entry.data[CONF_NAME],
            CONF_USERNAME: device.config_entry.data[CONF_USERNAME],
            CONF_PASSWORD: device.config_entry.data[CONF_PASSWORD],
            CONF_MJPEG_URL: self.mjpeg_source,
            CONF_STILL_IMAGE_URL: self.image_source,
            CONF_AUTHENTICATION: HTTP_DIGEST_AUTHENTICATION,
        }
        MjpegCamera.__init__(self, config)

    async def async_added_to_hass(self):
        """Subscribe camera events."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, self.device.signal_new_address, self._new_address
            )
        )

        await super().async_added_to_hass()

    @property
    def supported_features(self):
        """Return supported features."""
        return SUPPORT_STREAM

    def _new_address(self):
        """Set new device address for video stream."""
        self._mjpeg_url = self.mjpeg_source
        self._still_image_url = self.image_source

    @property
    def unique_id(self):
        """Return a unique identifier for this device."""
        return f"{self.device.serial}-camera"

    @property
    def image_source(self):
        """Return still image URL for device."""
        return f"http://{self.device.host}:{self.device.config_entry.data[CONF_PORT]}/axis-cgi/jpg/image.cgi"

    @property
    def mjpeg_source(self):
        """Return mjpeg URL for device."""
        options = ""
        if self.device.option_stream_profile != DEFAULT_STREAM_PROFILE:
            options = f"?&streamprofile={self.device.option_stream_profile}"

        return f"http://{self.device.host}:{self.device.config_entry.data[CONF_PORT]}/axis-cgi/mjpg/video.cgi{options}"

    async def stream_source(self):
        """Return the stream source."""
        options = ""
        if self.device.option_stream_profile != DEFAULT_STREAM_PROFILE:
            options = f"&streamprofile={self.device.option_stream_profile}"

        return f"rtsp://{self.device.config_entry.data[CONF_USERNAME]}:{self.device.config_entry.data[CONF_PASSWORD]}@{self.device.host}/axis-media/media.amp?videocodec=h264{options}"
