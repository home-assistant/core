"""Support for Imou camera entities."""

from pyimouapi.const import PARAM_HD, PARAM_MOTION_DETECT, PARAM_STATE
from pyimouapi.exceptions import ImouException
from pyimouapi.ha_device import ImouHaDevice

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import PARAM_HEADER_DETECT, imou_device_identifier
from .coordinator import ImouConfigEntry, ImouDataUpdateCoordinator
from .entity import ImouEntity

PARALLEL_UPDATES = 0

CAMERA_STREAM_RESOLUTION_SD = "SD"

# Defaults for pyimouapi ImouHaDeviceManager APIs (see async_get_stream_url).
PYIMOUAPI_LIVE_PROTOCOL = "https"
PYIMOUAPI_SNAPSHOT_WAIT_SECONDS = 3

CAMERA_TYPES = (
    ("camera_sd", CAMERA_STREAM_RESOLUTION_SD),
    ("camera_hd", PARAM_HD),
)


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
            ImouCamera(coordinator, entity_type, device, resolution)
            for device in coordinator.devices
            if device.channel_id is not None
            if imou_device_identifier(device) in device_keys
            for entity_type, resolution in CAMERA_TYPES
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
        entity_type: str,
        device: ImouHaDevice,
        resolution: str,
    ) -> None:
        """Initialize the camera entity."""
        self._resolution = resolution
        Camera.__init__(self)
        super().__init__(coordinator, entity_type, device)

    async def stream_source(self) -> str | None:
        """Return the live stream URL from the Imou cloud."""
        try:
            return await self.coordinator.device_manager.async_get_device_stream(
                self.device,
                self._resolution,
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
