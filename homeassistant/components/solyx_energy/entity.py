"""Base entity for the Solyx Energy integration."""

from typing import TYPE_CHECKING

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SolyxEnergyCoordinator

if TYPE_CHECKING:
    from homeassistant.helpers.entity import EntityDescription


class SolyxNymoEntity(CoordinatorEntity[SolyxEnergyCoordinator]):
    """Base class for the Nymo entity of the Solyx Energy integration."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SolyxEnergyCoordinator,
        description: EntityDescription,
    ) -> None:
        """Initialize a Solyx Nymo entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.device_id}-{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.device_id)},
            name="Nymo",
            manufacturer="Solyx Energy",
            model="Nymo",
            serial_number=coordinator.device_id,
        )
