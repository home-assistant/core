"""Support for Imou camera entities."""

from dataclasses import dataclass
from typing import Any

from pyimouapi.const import (
    PARAM_HD,
    PARAM_MOTION_DETECT,
    PARAM_STATE,
    PARAM_STORAGE_USED,
)
from pyimouapi.exceptions import ImouException
from pyimouapi.ha_device import ImouHaDevice

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import PARAM_HEADER_DETECT, imou_device_identifier
from .coordinator import ImouConfigEntry, ImouDataUpdateCoordinator
from .entity import ImouEntity

PARALLEL_UPDATES = 1

CAMERA_STREAM_RESOLUTION_SD = "SD"

# Defaults for pyimouapi ImouHaDeviceManager APIs (see async_get_stream_url).
PYIMOUAPI_LIVE_PROTOCOL = "https"
PYIMOUAPI_SNAPSHOT_WAIT_SECONDS = 3


@dataclass(frozen=True, kw_only=True)
class ImouCameraEntityDescription:
    """Description of an Imou camera entity for a device channel."""

    key: str
    resolution: str


CAMERA_ENTITIES = (
    ImouCameraEntityDescription(
        key="camera_sd", resolution=CAMERA_STREAM_RESOLUTION_SD
    ),
    ImouCameraEntityDescription(key="camera_hd", resolution=PARAM_HD),
)


def _iter_cameras(
    coordinator: ImouDataUpdateCoordinator,
) -> list[ImouHaDevice]:
    """Return devices that expose a camera channel."""
    return [device for device in coordinator.devices if device.channel_id is not None]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ImouConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Imou camera entities."""
    coordinator = entry.runtime_data

    def _add_cameras(new_devices: list[ImouHaDevice]) -> None:
        device_keys = {imou_device_identifier(device) for device in new_devices}
        async_add_entities(
            ImouCamera(coordinator, device, description)
            for device in _iter_cameras(coordinator)
            if imou_device_identifier(device) in device_keys
            for description in CAMERA_ENTITIES
        )

    coordinator.new_device_callbacks.append(_add_cameras)

    @callback
    def _remove_new_device_callback() -> None:
        if _add_cameras in coordinator.new_device_callbacks:
            coordinator.new_device_callbacks.remove(_add_cameras)

    entry.async_on_unload(_remove_new_device_callback)
    _add_cameras(coordinator.devices)


class ImouCamera(ImouEntity, Camera):
    """Representation of an Imou camera stream."""

    def __init__(
        self,
        coordinator: ImouDataUpdateCoordinator,
        device: ImouHaDevice,
        description: ImouCameraEntityDescription,
    ) -> None:
        """Initialize the camera entity."""
        self._camera_description = description
        Camera.__init__(self)
        super().__init__(coordinator, description.key, device)

    async def stream_source(self) -> str | None:
        """Return the live stream URL from the Imou cloud."""
        try:
            return await self.coordinator.device_manager.async_get_device_stream(
                self.device,
                self._camera_description.resolution,
                PYIMOUAPI_LIVE_PROTOCOL,
            )
        except ImouException as err:
            raise HomeAssistantError(str(err)) from err

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return bytes of camera image."""
        try:
            return await self.coordinator.device_manager.async_get_device_image(
                self.device,
                PYIMOUAPI_SNAPSHOT_WAIT_SECONDS,
            )
        except ImouException as err:
            raise HomeAssistantError(str(err)) from err

    @property
    def is_recording(self) -> bool:
        """Return True when storage reports usage and motion detection is enabled."""
        storage = self.device.sensors.get(PARAM_STORAGE_USED)
        storage_state = storage[PARAM_STATE] if storage else "-1"
        return (
            self._is_non_negative_number(storage_state)
            and self.motion_detection_enabled
        )

    @property
    def motion_detection_enabled(self) -> bool:
        """Return True when human and/or motion detection switch is on."""
        header = self.device.switches.get(PARAM_HEADER_DETECT)
        motion = self.device.switches.get(PARAM_MOTION_DETECT)
        header_on = bool(header[PARAM_STATE]) if header else False
        motion_on = bool(motion[PARAM_STATE]) if motion else False
        return header_on or motion_on

    @property
    def supported_features(self) -> CameraEntityFeature:
        """Flag streaming support."""
        return CameraEntityFeature.STREAM

    @staticmethod
    def _is_non_negative_number(value: Any) -> bool:
        """Return True if value parses as a non-negative number."""
        try:
            number = float(value)
        except TypeError, ValueError:
            return False
        return number >= 0
