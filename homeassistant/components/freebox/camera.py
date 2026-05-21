"""Support for Freebox cameras."""

from typing import Any

from aiohttp import web
from haffmpeg.camera import CameraMjpeg
from haffmpeg.tools import IMAGE_JPEG

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.components.ffmpeg import DATA_FFMPEG, FFmpegManager, async_get_image
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_platform
from homeassistant.helpers.aiohttp_client import async_aiohttp_proxy_stream
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import ATTR_DETECTION, FreeboxHomeCategory
from .entity import FreeboxHomeEntity
from .router import FreeboxConfigEntry, FreeboxRouter

_FFMPEG_ARGUMENTS = "-pred 1"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FreeboxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up cameras."""
    router = entry.runtime_data
    tracked: set[str] = set()

    @callback
    def update_callback() -> None:
        add_entities(hass, router, async_add_entities, tracked)

    router.listeners.append(
        async_dispatcher_connect(hass, router.signal_home_device_new, update_callback)
    )
    update_callback()

    entity_platform.async_get_current_platform()


@callback
def add_entities(
    hass: HomeAssistant,
    router: FreeboxRouter,
    async_add_entities: AddConfigEntryEntitiesCallback,
    tracked: set[str],
) -> None:
    """Add new cameras from the router."""
    new_tracked: list[FreeboxCamera] = []

    for nodeid, node in router.home_devices.items():
        if (node["category"] != FreeboxHomeCategory.CAMERA) or (nodeid in tracked):
            continue
        new_tracked.append(FreeboxCamera(hass, router, node))
        tracked.add(nodeid)

    if new_tracked:
        async_add_entities(new_tracked, True)


class FreeboxCamera(FreeboxHomeEntity, Camera):
    """Representation of a Freebox camera."""

    _attr_name = None
    _attr_supported_features = CameraEntityFeature.ON_OFF | CameraEntityFeature.STREAM

    def __init__(
        self, hass: HomeAssistant, router: FreeboxRouter, node: dict[str, Any]
    ) -> None:
        """Initialize a camera."""
        super().__init__(router, node)
        Camera.__init__(self)

        self._ffmpeg: FFmpegManager = hass.data[DATA_FFMPEG]
        self._input: str = node["props"]["Stream"]

        self._command_motion_detection = self.get_command_id(
            node["type"]["endpoints"], "slot", ATTR_DETECTION
        )
        self._attr_extra_state_attributes = {}
        self.update_node(node)

    async def stream_source(self) -> str:
        """Return the stream source."""
        return self._input.split(" ")[-1]

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a still image response from the camera."""
        return await async_get_image(
            self.hass,
            self._input,
            output_format=IMAGE_JPEG,
            extra_cmd=_FFMPEG_ARGUMENTS,
        )

    async def handle_async_mjpeg_stream(
        self, request: web.Request
    ) -> web.StreamResponse:
        """Generate an HTTP MJPEG stream from the camera."""
        stream = CameraMjpeg(self._ffmpeg.binary)
        await stream.open_camera(self._input, extra_cmd=_FFMPEG_ARGUMENTS)

        try:
            stream_reader = await stream.get_reader()
            return await async_aiohttp_proxy_stream(
                self.hass,
                request,
                stream_reader,
                self._ffmpeg.ffmpeg_stream_content_type,
            )
        finally:
            await stream.close()

    async def async_enable_motion_detection(self) -> None:
        """Enable motion detection in the camera."""
        if await self.set_home_endpoint_value(self._command_motion_detection, True):
            self._attr_motion_detection_enabled = True

    async def async_disable_motion_detection(self) -> None:
        """Disable motion detection in camera."""
        if await self.set_home_endpoint_value(self._command_motion_detection, False):
            self._attr_motion_detection_enabled = False

    async def async_update_signal(self) -> None:
        """Update the camera node."""
        self.update_node(self._router.home_devices[self._id])
        await super().async_update_signal()

    def update_node(self, node: dict[str, Any]) -> None:
        """Update params."""
        self._attr_is_streaming = node["status"] == "active"

        for endpoint in filter(
            lambda x: x["ep_type"] == "signal", node["show_endpoints"]
        ):
            self._attr_extra_state_attributes[endpoint["name"]] = endpoint["value"]

        self._attr_motion_detection_enabled = self._attr_extra_state_attributes[
            ATTR_DETECTION
        ]
