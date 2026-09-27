"""Support for Vivotek IP Cameras."""

from collections.abc import Callable
from functools import partial
import logging
from typing import TYPE_CHECKING, Any, Final, override

from libpyvivotek.vivotek import VivotekCamera, VivotekCameraError

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device_registry import DeviceInfo
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


def _fetch_str_metadata(
    fetcher: Callable[[], Any],
    log_message: str,
) -> str | None:
    """Fetch optional string metadata from the camera."""
    try:
        value: Any = fetcher()
    except VivotekCameraError:
        _LOGGER.debug(log_message)
        return None

    return value if isinstance(value, str) else None


def _fetch_metadata(
    cam_client: VivotekCamera, entry_title: str
) -> tuple[str | None, ...]:
    """Fetch optional metadata from the camera in a single executor job."""
    return (
        _fetch_str_metadata(
            cam_client.get_serial,
            f"Failed to fetch serial number for {entry_title}",
        ),
        _fetch_str_metadata(
            partial(cam_client.get_param, "system_info_firmwareversion"),
            f"Failed to fetch firmware version for {entry_title}",
        ),
        _fetch_str_metadata(
            partial(cam_client.get_param, "system_info_modelname"),
            f"Failed to fetch model for {entry_title}",
        ),
    )


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
    serial_number, sw_version, model = await hass.async_add_executor_job(
        _fetch_metadata,
        cam_client,
        entry.title,
    )

    if TYPE_CHECKING:
        assert entry.unique_id is not None
    async_add_entities(
        [
            VivotekCam(
                cam_client,
                stream_source,
                entry.unique_id,
                serial_number,
                sw_version,
                model,
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
        serial_number: str | None,
        sw_version: str | None,
        model: str | None,
        framerate: int,
        name: str,
    ) -> None:
        """Initialize a Vivotek camera."""
        super().__init__()
        self._cam = cam_client
        self._attr_frame_interval = 1 / framerate
        self._attr_unique_id = unique_id
        self._attr_name = name
        self._attr_available = True
        self._stream_source = stream_source
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            manufacturer=DEFAULT_CAMERA_BRAND,
            model=model,
            name=name,
            serial_number=serial_number,
            sw_version=sw_version,
        )

    @override
    def camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return bytes of camera image."""
        return self._cam.snapshot()

    @override
    async def stream_source(self) -> str:
        """Return the source of the stream."""
        return self._stream_source

    @override
    def disable_motion_detection(self) -> None:
        """Disable motion detection in camera."""
        response = self._cam.set_param(DEFAULT_EVENT_0_KEY, 0)
        self._attr_motion_detection_enabled = int(response) == 1

    @override
    def enable_motion_detection(self) -> None:
        """Enable motion detection in camera."""
        response = self._cam.set_param(DEFAULT_EVENT_0_KEY, 1)
        self._attr_motion_detection_enabled = int(response) == 1

    def update(self) -> None:
        """Update entity status."""
        try:
            self._cam.get_serial()
        except VivotekCameraError:
            self._attr_available = False
        else:
            self._attr_available = True
