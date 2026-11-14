"""Light platform for the Bosch Smart Camera integration."""

from typing import Any, override

from bosch_shc_camera_client.cameras import CameraModel

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import BoschCameraConfigEntry, BoschCameraCoordinator

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BoschCameraConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the camera lights of the account."""
    coordinator = entry.runtime_data
    known: set[str] = set()

    @callback
    def _add_new_lights() -> None:
        # Forget removed cameras so one that comes back gets a new entity.
        known.intersection_update(coordinator.data)
        new = {
            camera_id
            for camera_id, camera in coordinator.data.items()
            if camera.model is CameraModel.EYES_OUTDOOR
        } - known
        known.update(new)
        async_add_entities(
            BoschCameraLight(coordinator, camera_id) for camera_id in new
        )

    entry.async_on_unload(coordinator.async_add_listener(_add_new_lights))
    _add_new_lights()


class BoschCameraLight(CoordinatorEntity[BoschCameraCoordinator], LightEntity):
    """The light of a camera, switchable on and off."""

    _attr_has_entity_name = True
    _attr_translation_key = "camera_light"
    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}

    def __init__(self, coordinator: BoschCameraCoordinator, camera_id: str) -> None:
        """Initialize the light."""
        super().__init__(coordinator)
        self._camera_id = camera_id
        self._attr_unique_id = camera_id
        # Platforms set up concurrently, so either may be first to create the device.
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, camera_id)},
            manufacturer="Bosch",
            name=coordinator.data[camera_id].title,
        )

    @property
    @override
    def available(self) -> bool:
        """Return whether the camera light state is known."""
        return super().available and self._camera_id in self.coordinator.light_states

    @property
    @override
    def is_on(self) -> bool:
        """Return whether the light is on."""
        return self.coordinator.light_states[self._camera_id].any_on

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        await self.coordinator.async_set_light(self._camera_id, True)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self.coordinator.async_set_light(self._camera_id, False)
