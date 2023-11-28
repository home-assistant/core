"""Base entity class for DROP entities."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import DROP_DeviceDataUpdateCoordinator


class DROP_Entity(CoordinatorEntity[DROP_DeviceDataUpdateCoordinator]):
    """Representation of a DROP device entity."""

    _attr_force_update = False
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self, entity_type: str, coordinator: DROP_DeviceDataUpdateCoordinator
    ) -> None:
        """Init DROP entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.id}_{entity_type}"
        self._device: DROP_DeviceDataUpdateCoordinator = coordinator

    @property
    def device_info(self) -> DeviceInfo:
        """Return a device description for device registry."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device.id)},
            manufacturer=self._device.manufacturer,
            model=self._device.model,
            name=self._device.device_name,
        )
