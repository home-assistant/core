"""Setup for a generic entity type for the Cync integration."""

from pycync.devices import CyncControllable

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import CyncCoordinator


class CyncBaseEntity(CoordinatorEntity[CyncCoordinator]):
    """Generic base entity for Cync devices."""

    _attr_has_entity_name = True

    def __init__(
        self,
        device: CyncControllable,
        coordinator: CyncCoordinator,
        room_name: str | None = None,
    ) -> None:
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)

        self._device = device
        self._attr_unique_id = device.unique_id
        self._attr_name = device.name
        self._room_name = room_name

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device.unique_id)},
            manufacturer="GE Lighting",
            name=self._device.name,
            suggested_area=self._room_name,
        )
