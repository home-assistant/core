"""Setup for a generic entity type for the Cync integration."""

from pycync.devices import CyncDevice

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import CyncCoordinator


class CyncBaseEntity(CoordinatorEntity[CyncCoordinator]):
    """Generic base entity for Cync devices."""

    _attr_has_entity_name = True

    def __init__(
        self,
        device: CyncDevice,
        coordinator: CyncCoordinator,
        room_name: str | None = None,
    ) -> None:
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)

        self._cync_device_id = device.device_id
        self._attr_unique_id = device.unique_id

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.unique_id)},
            manufacturer="GE Lighting",
            name=device.name,
            suggested_area=room_name,
        )

    @property
    def available(self) -> bool:
        """Determines whether this device is currently available."""

        return (
            super().available
            and self.coordinator.data is not None
            and self._cync_device_id in self.coordinator.data
            and self.coordinator.data[self._cync_device_id].is_online
        )
