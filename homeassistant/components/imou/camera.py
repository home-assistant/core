"""Support for Imou camera entities."""

from typing import Any

from pyimouapi.const import PARAM_MOTION_DETECT, PARAM_STATE, PARAM_STORAGE_USED
from pyimouapi.exceptions import ImouException
from pyimouapi.ha_device import ImouHaDevice

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CONF_OPTION_LIVE_RESOLUTION,
    DEFAULT_LIVE_RESOLUTION,
    PARAM_HEADER_DETECT,
    PYIMOUAPI_LIVE_RESOLUTIONS,
    imou_device_identifier,
)
from .coordinator import ImouConfigEntry, ImouDataUpdateCoordinator
from .entity import ImouEntity

PARALLEL_UPDATES = 1

ENTITY_TYPE_CAMERA = "camera"

# Defaults for pyimouapi ImouHaDeviceManager APIs without HA options (see async_get_stream_url).
PYIMOUAPI_LIVE_PROTOCOL = "https"
PYIMOUAPI_SNAPSHOT_WAIT_SECONDS = 3


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
            ImouCamera(coordinator, device)
            for device in _iter_cameras(coordinator)
            if imou_device_identifier(device) in device_keys
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
    ) -> None:
        """Initialize the camera entity."""
        Camera.__init__(self)
        super().__init__(coordinator, ENTITY_TYPE_CAMERA, device)

    async def stream_source(self) -> str | None:
        """Return the live stream URL from the Imou cloud."""
        options = self.coordinator.config_entry.options
        resolution = options.get(
            CONF_OPTION_LIVE_RESOLUTION, DEFAULT_LIVE_RESOLUTION
        )
        try:
            return await self.coordinator.device_manager.async_get_device_stream(
                self.device,
                PYIMOUAPI_LIVE_RESOLUTIONS[resolution],
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
    def is_streaming(self) -> bool:
        """Return True when the camera stream worker is running."""
        if self.stream is None:
            return False
        return self.stream._thread is not None and self.stream._thread.is_alive()  # noqa: SLF001

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
