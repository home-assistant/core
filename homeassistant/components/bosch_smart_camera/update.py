"""Update platform for the Bosch Smart Camera integration."""

from typing import override

from homeassistant.components.update import UpdateEntity, UpdateEntityFeature
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import BoschCameraConfigEntry, BoschFirmwareCoordinator

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BoschCameraConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the firmware entities of the cameras."""
    cameras = entry.runtime_data
    coordinator = cameras.firmware
    known: set[str] = set()

    @callback
    def _add_new_cameras() -> None:
        # Forget removed cameras so one that comes back gets a new entity.
        known.intersection_update(cameras.data)
        new = set(cameras.data) - known
        known.update(new)
        async_add_entities(BoschFirmware(coordinator, camera_id) for camera_id in new)

    entry.async_on_unload(cameras.async_add_listener(_add_new_cameras))
    _add_new_cameras()


class BoschFirmware(CoordinatorEntity[BoschFirmwareCoordinator], UpdateEntity):
    """The firmware of a camera, which Bosch installs on its own."""

    _attr_auto_update = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True
    _attr_supported_features = UpdateEntityFeature.PROGRESS
    _attr_translation_key = "firmware"

    def __init__(self, coordinator: BoschFirmwareCoordinator, camera_id: str) -> None:
        """Initialize the update entity."""
        super().__init__(coordinator)
        self._camera_id = camera_id
        self._attr_unique_id = f"{camera_id}_firmware"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, camera_id)},
            name=coordinator.cameras.data[camera_id].title,
        )

    @override
    async def async_added_to_hass(self) -> None:
        """Follow the installed version published by the camera list."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.cameras.async_add_listener(self.async_write_ha_state)
        )

    @property
    @override
    def installed_version(self) -> str | None:
        """Return the installed firmware version."""
        camera = self.coordinator.cameras.data[self._camera_id]
        return camera.firmware_version

    @property
    @override
    def latest_version(self) -> str | None:
        """Return the available firmware version, or the installed one."""
        status = self.coordinator.data[self._camera_id]
        if status.up_to_date is False and status.update:
            return status.update
        return self.installed_version

    @property
    @override
    def in_progress(self) -> bool:
        """Return whether the camera is installing a firmware update."""
        return self.coordinator.data[self._camera_id].updating

    @property
    @override
    def available(self) -> bool:
        """Return whether both the camera list and firmware status know the camera."""
        return (
            super().available
            and self.coordinator.cameras.last_update_success
            and self._camera_id in self.coordinator.data
            and self._camera_id in self.coordinator.cameras.data
        )
