"""Base entity for Mill devices."""

from __future__ import annotations

from abc import abstractmethod

from mill import Heater, MillDevice

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import MillDataUpdateCoordinator


class MillBaseEntity(CoordinatorEntity[MillDataUpdateCoordinator]):
    """Representation of a Mill number device."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MillDataUpdateCoordinator,
        mill_device: MillDevice,
    ) -> None:
        """Initialize the number."""
        super().__init__(coordinator)

        self._id = mill_device.device_id
        self._available = False
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, mill_device.device_id)},
            name=mill_device.name,
            manufacturer=MANUFACTURER,
            model=mill_device.model,
        )
        self._update_attr(mill_device)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_attr(self.coordinator.data[self._id])
        self.async_write_ha_state()

    @abstractmethod
    @callback
    def _update_attr(self, device: MillDevice | Heater) -> None:
        """Update the attribute of the entity."""

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self._available
