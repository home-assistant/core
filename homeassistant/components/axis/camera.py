"""Support for Axis camera streaming."""

from urllib.parse import urlencode

from homeassistant.components.camera import CameraEntityFeature
from homeassistant.components.mjpeg import MjpegCamera, filter_urllib3_logging
from homeassistant.const import HTTP_DIGEST_AUTHENTICATION
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AxisConfigEntry
from .const import DEFAULT_STREAM_PROFILE, DEFAULT_VIDEO_SOURCE
from .entity import AxisEntity
from .hub import AxisHub


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: AxisConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Axis camera video stream."""
    filter_urllib3_logging()

    hub = config_entry.runtime_data

    if (
        not (prop := hub.api.vapix.params.property_handler.get("0"))
        or not prop.image_format
    ):
        return

    async_add_entities([AxisCamera(hub)])


class AxisCamera(AxisEntity, MjpegCamera):
    """Representation of a Axis camera."""

    _attr_supported_features = CameraEntityFeature.STREAM

    _still_image_url: str
    _mjpeg_url: str
    _stream_source: str

    def __init__(self, hub: AxisHub) -> None:
        """Initialize Axis Communications camera component."""
        AxisEntity.__init__(self, hub)

        self._generate_sources()

        MjpegCamera.__init__(
            self,
            username=hub.config.username,
            password=hub.config.password,
            mjpeg_url=self.mjpeg_source,
            still_image_url=self.image_source,
            authentication=HTTP_DIGEST_AUTHENTICATION,
            verify_ssl=False,
            unique_id=f"{hub.unique_id}-camera",
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe camera events."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, self.hub.signal_new_address, self._generate_sources
            )
        )

        await super().async_added_to_hass()

    def _generate_sources(self) -> None:
        """Generate sources.

        Additionally used when device change IP address.
        """
        proto = self.hub.config.protocol
        host = self.hub.config.host
        port = self.hub.config.port

        image_options = self.generate_options(skip_stream_profile=True)
        self._still_image_url = (
            f"{proto}://{host}:{port}/axis-cgi/jpg/image.cgi{image_options}"
        )

        mjpeg_options = self.generate_options()
        self._mjpeg_url = (
            f"{proto}://{host}:{port}/axis-cgi/mjpg/video.cgi{mjpeg_options}"
        )

        stream_options = self.generate_options(add_video_codec_h264=True)
        self._stream_source = (
            f"rtsp://{self.hub.config.username}:{self.hub.config.password}"
            f"@{self.hub.config.host}/axis-media/media.amp{stream_options}"
        )

        self.hub.additional_diagnostics["camera_sources"] = {
            "Image": self._still_image_url,
            "MJPEG": self._mjpeg_url,
            "Stream": (f"rtsp://user:pass@{host}/axis-media/media.amp{stream_options}"),
        }

    @property
    def image_source(self) -> str:
        """Return still image URL for device."""
        return self._still_image_url

    @property
    def mjpeg_source(self) -> str:
        """Return mjpeg URL for device."""
        return self._mjpeg_url

    async def stream_source(self) -> str:
        """Return the stream source."""
        return self._stream_source

    def generate_options(
        self, skip_stream_profile: bool = False, add_video_codec_h264: bool = False
    ) -> str:
        """Generate options for video stream."""
        options_dict = {}

        if add_video_codec_h264:
            options_dict["videocodec"] = "h264"

        if (
            not skip_stream_profile
            and self.hub.config.stream_profile != DEFAULT_STREAM_PROFILE
        ):
            options_dict["streamprofile"] = self.hub.config.stream_profile

        if self.hub.config.video_source != DEFAULT_VIDEO_SOURCE:
            options_dict["camera"] = self.hub.config.video_source

        if not options_dict:
            return ""
        return f"?{urlencode(options_dict)}"
