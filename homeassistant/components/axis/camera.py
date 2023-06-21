"""Support for Axis camera streaming."""
from urllib.parse import urlencode

from homeassistant.components.camera import CameraEntityFeature
from homeassistant.components.mjpeg import MjpegCamera, filter_urllib3_logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import HTTP_DIGEST_AUTHENTICATION
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DEFAULT_STREAM_PROFILE, DEFAULT_VIDEO_SOURCE, DOMAIN as AXIS_DOMAIN
from .device import AxisNetworkDevice
from .entity import AxisEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Axis camera video stream."""
    filter_urllib3_logging()

    device: AxisNetworkDevice = hass.data[AXIS_DOMAIN][config_entry.entry_id]

    if not device.api.vapix.params.image_format:
        return

    async_add_entities([AxisCamera(device)])


class AxisCamera(AxisEntity, MjpegCamera):
    """Representation of a Axis camera."""

    _attr_supported_features = CameraEntityFeature.STREAM

    def __init__(self, device: AxisNetworkDevice) -> None:
        """Initialize Axis Communications camera component."""
        AxisEntity.__init__(self, device)

        MjpegCamera.__init__(
            self,
            username=device.username,
            password=device.password,
            mjpeg_url=self.mjpeg_source,
            still_image_url=self.image_source,
            authentication=HTTP_DIGEST_AUTHENTICATION,
        )

        self._attr_unique_id = f"{device.unique_id}-camera"

    async def async_added_to_hass(self) -> None:
        """Subscribe camera events."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, self.device.signal_new_address, self._new_address
            )
        )

        await super().async_added_to_hass()

    def _new_address(self) -> None:
        """Set new device address for video stream."""
        self._mjpeg_url = self.mjpeg_source
        self._still_image_url = self.image_source

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
