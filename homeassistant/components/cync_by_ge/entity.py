"""Setup for a generic entity type for the Cync integration."""

from pycync.devices import CyncControllable

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import CyncCoordinator


class CyncBaseEntity(CoordinatorEntity):
    """Generic base entity for Cync devices."""

    def __init__(
        self, device: CyncControllable, coordinator: CyncCoordinator, room_name=None
    ) -> None:
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)

        self._device = device
        self._attr_unique_id = device.unique_id
        self._name = device.name
        self._room_name = room_name

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{self._device.unique_id}")},
            manufacturer="GE Lighting",
            name=self._device.name,
            suggested_area=self._room_name,
        )

    @property
    def name(self) -> str:
        """Return the entity's name."""
        return self._name

    async def async_added_to_hass(self) -> None:
        """Add device to hass."""
        await super().async_added_to_hass()

    async def async_will_remove_from_hass(self) -> None:
        """Remove device from hass."""
        await super().async_will_remove_from_hass()
