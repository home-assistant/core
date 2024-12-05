import logging

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ImouDataUpdateCoordinator
from .entity import ImouEntity
from .const import DOMAIN, PARAM_MOTION_DETECT, PARAM_STORAGE_USED
from pyimouapi.ha_device import ImouHaDevice
from pyimouapi.exceptions import ImouException

_LOGGER: logging.Logger = logging.getLogger(__package__)


async def async_setup_entry(
        hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    imou_coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for device in imou_coordinator.devices:
        entities.append(ImouCamera(imou_coordinator, entry, device))
    async_add_entities(entities)


class ImouCamera(ImouEntity, Camera):
    """imou camera"""
    _attr_supported_features = CameraEntityFeature.STREAM

    def __init__(self, coordinator: ImouDataUpdateCoordinator, config_entry: ConfigEntry, device: ImouHaDevice):
        """Initialize."""
        Camera.__init__(self)
        ImouEntity.__init__(
            self, coordinator, config_entry, "camera", device)

    async def stream_source(self) -> str | None:
        """GET STREAMING ADDRESS"""
        try:
            return await self.coordinator.device_manager.async_get_device_stream(self._device)
        except ImouException as e:
            raise HomeAssistantError(e.message)

    async def async_camera_image(
            self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        try:
            """Return bytes of camera image."""
            return await self.coordinator.device_manager.async_get_device_image(self._device)
        except ImouException as e:
            raise HomeAssistantError(e.message)

    @property
    def is_recording(self) -> bool:
        # The battery level is normal and the motion detect is activated, indicating that it is in  recording mode
        return "%" in self._device.sensors[PARAM_STORAGE_USED] and self._device.switches[PARAM_MOTION_DETECT]

    @property
    def is_streaming(self) -> bool:
        if self.stream is None:
            return False
        return self.stream._thread is not None and self.stream._thread.is_alive()

    @property
    def motion_detection_enabled(self) -> bool:
        """Camera Motion Detection Status."""
        return self._device.switches[PARAM_MOTION_DETECT]
