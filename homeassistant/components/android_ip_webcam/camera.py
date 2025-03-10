"""Support for Android IP Webcam Cameras."""

from __future__ import annotations

from homeassistant.components.camera import CameraEntityFeature
from homeassistant.components.mjpeg import MjpegCamera, filter_urllib3_logging
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_PASSWORD,
    CONF_USERNAME,
    HTTP_BASIC_AUTHENTICATION,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import AndroidIPCamConfigEntry, AndroidIPCamDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: AndroidIPCamConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the IP Webcam camera from config entry."""
    filter_urllib3_logging()
    async_add_entities([IPWebcamCamera(config_entry.runtime_data)])


class IPWebcamCamera(MjpegCamera):
    """Representation of a IP Webcam camera."""

    _attr_has_entity_name = True
    _attr_supported_features = CameraEntityFeature.STREAM

    def __init__(self, coordinator: AndroidIPCamDataUpdateCoordinator) -> None:
        """Initialize the camera."""
        self._cam_username = coordinator.config_entry.data.get(CONF_USERNAME)
        self._cam_password = coordinator.config_entry.data.get(CONF_PASSWORD, "")
        super().__init__(
            mjpeg_url=coordinator.cam.mjpeg_url,
            still_image_url=coordinator.cam.image_url,
            authentication=HTTP_BASIC_AUTHENTICATION,
            username=self._cam_username,
            password=self._cam_password,
        )
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}-camera"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            name=coordinator.config_entry.data[CONF_HOST],
        )
        self._coordinator = coordinator

    async def stream_source(self) -> str:
        """Get the stream source for the Android IP camera."""
        coordinator_is_ssl = self._coordinator.cam.base_url.startswith(
            "https"
        )  # avoid accessing private attribute
        rtsp_protocol = "rtsps" if coordinator_is_ssl else "rtsp"

        host = self._coordinator.config_entry.data[CONF_HOST]
        port = self._coordinator.config_entry.data[CONF_PORT]

        video_codec = "h264"  # most compatible & recommended
        # while "opus" is compatible with more devices, HA's stream integration requires AAC or MP3,
        # and IP webcam doesn't provide MP3 audio. aac is supported on select devices >= android 4.1
        # the stream will be quiet on devices that don't support aac, but it won't fail.
        audio_codec = "aac"

        if self._cam_username and self._cam_password:
            return (
                f"{rtsp_protocol}://{self._cam_username}:{self._cam_password}@{host}:{port}"
                f"/{video_codec}_{audio_codec}.sdp"
            )
        else:
            return (
                f"{rtsp_protocol}://{host}:{port}" f"/{video_codec}_{audio_codec}.sdp"
            )
