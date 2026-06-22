"""Support for Vivotek IP Cameras."""

import logging
from typing import TYPE_CHECKING, Final

from libpyvivotek.vivotek import VivotekCamera

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import VivotekConfigEntry
from .const import CONF_FRAMERATE, CONF_STREAM_PATH, DOMAIN

_LOGGER = logging.getLogger(__name__)

DEFAULT_CAMERA_BRAND = "VIVOTEK"
DEFAULT_NAME = "VIVOTEK Camera"
DEFAULT_EVENT_0_KEY = "event_i0_enable"
DEFAULT_FRAMERATE = 2
DEFAULT_SECURITY_LEVEL = "admin"
DEFAULT_STREAM_SOURCE = "live.sdp"

PLATFORM_SCHEMA: Final = cv.removed(DOMAIN, raise_if_present=False)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VivotekConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the component from a config entry."""
    config = entry.data
    creds = f"{config[CONF_USERNAME]}:{config[CONF_PASSWORD]}"
    stream_source = (
        f"rtsp://{creds}@{config[CONF_IP_ADDRESS]}:554/{config[CONF_STREAM_PATH]}"
    )
    cam_client = entry.runtime_data
    if TYPE_CHECKING:
        assert entry.unique_id is not None
    async_add_entities(
        [
            VivotekCam(
                cam_client,
                stream_source,
                entry.unique_id,
                entry.options[CONF_FRAMERATE],
                entry.title,
            )
        ]
    )


class VivotekCam(Camera):
    """A Vivotek IP camera."""

    _attr_brand = DEFAULT_CAMERA_BRAND
    _attr_supported_features = CameraEntityFeature.STREAM

    def __init__(
        self,
        cam_client: VivotekCamera,
        stream_source: str,
        unique_id: str,
        framerate: int,
        name: str,
    ) -> None:
        """Initialize a Vivotek camera."""
        super().__init__()
        self._cam = cam_client
        self._attr_frame_interval = 1 / framerate
        self._attr_unique_id = unique_id
        self._attr_name = name
        self._stream_source = stream_source

    def camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return bytes of camera image."""
        return self._cam.snapshot()

    async def stream_source(self) -> str:
        """Return the source of the stream."""
        return self._stream_source

    def disable_motion_detection(self) -> None:
        """Disable motion detection in camera."""
        response = self._cam.set_param(DEFAULT_EVENT_0_KEY, 0)
        self._attr_motion_detection_enabled = int(response) == 1

    def enable_motion_detection(self) -> None:
        """Enable motion detection in camera."""
        response = self._cam.set_param(DEFAULT_EVENT_0_KEY, 1)
        self._attr_motion_detection_enabled = int(response) == 1

    def update(self) -> None:
        """Update entity status."""
        self._attr_model = self._cam.model_name
        self._attr_available = self._attr_model is not None
