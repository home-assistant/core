"""Support for Tuya cameras."""

from __future__ import annotations

from tuya_device_handlers.definition.camera import (
    TuyaCameraDefinition,
    get_default_definition,
)
from tuya_sharing import CustomerDevice, Manager

from homeassistant.components import ffmpeg
from homeassistant.components.camera import (
    Camera as CameraEntity,
    CameraEntityDescription,
    CameraEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import TUYA_DISCOVERY_NEW, DeviceCategory
from .coordinator import TuyaConfigEntry
from .entity import TuyaEntity

CAMERAS: dict[DeviceCategory, CameraEntityDescription] = {
    DeviceCategory.DGHSXJ: CameraEntityDescription(key=""),
    DeviceCategory.SP: CameraEntityDescription(key=""),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TuyaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Tuya cameras dynamically through Tuya discovery."""
    manager = entry.runtime_data.manager

    @callback
    def async_discover_device(device_ids: list[str]) -> None:
        """Discover and add a discovered Tuya camera."""
        entities: list[TuyaCameraEntity] = []
        for device_id in device_ids:
            device = manager.device_map[device_id]
            if description := CAMERAS.get(device.category):
                entities.append(
                    TuyaCameraEntity(
                        device, manager, description, get_default_definition(device)
                    )
                )

        async_add_entities(entities)

    async_discover_device([*manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class TuyaCameraEntity(TuyaEntity, CameraEntity):
    """Tuya Camera Entity."""

    _attr_supported_features = CameraEntityFeature.STREAM
    _attr_brand = "Tuya"
    _attr_name = None

    def __init__(
        self,
        device: CustomerDevice,
        device_manager: Manager,
        description: CameraEntityDescription,
        definition: TuyaCameraDefinition,
    ) -> None:
        """Init Tuya Camera."""
        super().__init__(device, device_manager, description)
        CameraEntity.__init__(self)
        self._attr_model = device.product_name
        self._motion_detection_switch = definition.motion_detection_switch
        self._recording_status = definition.recording_status

    @property
    def is_recording(self) -> bool:
        """Return true if the device is recording."""
        if (status := self._read_wrapper(self._recording_status)) is not None:
            return status
        return False

    @property
    def motion_detection_enabled(self) -> bool:
        """Return the camera motion detection status."""
        if (status := self._read_wrapper(self._motion_detection_switch)) is not None:
            return status
        return False

    async def stream_source(self) -> str | None:
        """Return the source of the stream."""
        return await self.hass.async_add_executor_job(
            self.device_manager.get_device_stream_allocate,
            self.device.id,
            "rtsp",
        )

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a still image response from the camera."""
        stream_source = await self.stream_source()
        if not stream_source:
            return None
        return await ffmpeg.async_get_image(
            self.hass,
            stream_source,
            width=width,
            height=height,
        )

    async def async_enable_motion_detection(self) -> None:
        """Enable motion detection in the camera."""
        await self._async_send_wrapper_updates(self._motion_detection_switch, True)

    async def async_disable_motion_detection(self) -> None:
        """Disable motion detection in camera."""
        await self._async_send_wrapper_updates(self._motion_detection_switch, False)
