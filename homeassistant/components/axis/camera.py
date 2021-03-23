"""Support for Axis camera streaming."""

from urllib.parse import urlencode

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
    CONF_USERNAME,
    HTTP_DIGEST_AUTHENTICATION,
)
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .axis_base import AxisEntityBase
from .const import DEFAULT_STREAM_PROFILE, DEFAULT_VIDEO_SOURCE, DOMAIN as AXIS_DOMAIN


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
            CONF_NAME: device.name,
            CONF_USERNAME: device.username,
            CONF_PASSWORD: device.password,
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
    def supported_features(self) -> int:
        """Return supported features."""
        return SUPPORT_STREAM

    def _new_address(self) -> None:
        """Set new device address for video stream."""
        self._mjpeg_url = self.mjpeg_source
        self._still_image_url = self.image_source

    @property
    def unique_id(self) -> str:
        """Return a unique identifier for this device."""
        return f"{self.device.unique_id}-camera"

    @property
    def image_source(self) -> str:
        """Return still image URL for device."""
        options = self.generate_options(skip_stream_profile=True)
        return f"http://{self.device.host}:{self.device.port}/axis-cgi/jpg/image.cgi{options}"

    @property
    def mjpeg_source(self) -> str:
        """Return mjpeg URL for device."""
        options = self.generate_options()
        return f"http://{self.device.host}:{self.device.port}/axis-cgi/mjpg/video.cgi{options}"

    async def stream_source(self) -> str:
        """Return the stream source."""
        options = self.generate_options(add_video_codec_h264=True)
        return f"rtsp://{self.device.username}:{self.device.password}@{self.device.host}/axis-media/media.amp{options}"

    def generate_options(
        self, skip_stream_profile: bool = False, add_video_codec_h264: bool = False
    ) -> str:
        """Generate options for video stream."""
        options_dict = {}

        if add_video_codec_h264:
            options_dict["videocodec"] = "h264"

        if (
            not skip_stream_profile
            and self.device.option_stream_profile != DEFAULT_STREAM_PROFILE
        ):
            options_dict["streamprofile"] = self.device.option_stream_profile

        if self.device.option_video_source != DEFAULT_VIDEO_SOURCE:
            options_dict["camera"] = self.device.option_video_source

        if not options_dict:
            return ""
        return f"?{urlencode(options_dict)}"
