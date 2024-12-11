"""Base class for Acaia entities."""

from dataclasses import dataclass

from homeassistant.helpers.device_registry import (
    CONNECTION_BLUETOOTH,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AcaiaCoordinator


@dataclass
class AcaiaEntity(CoordinatorEntity[AcaiaCoordinator]):
    """Common elements for all entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AcaiaCoordinator,
        entity_description: EntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._scale = coordinator.scale
        formatted_mac = format_mac(self._scale.mac)
        self._attr_unique_id = f"{formatted_mac}_{entity_description.key}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, formatted_mac)},
            manufacturer="Acaia",
            model=self._scale.model,
            suggested_area="Kitchen",
            connections={(CONNECTION_BLUETOOTH, self._scale.mac)},
        )

    @property
    def available(self) -> bool:
        """Returns whether entity is available."""
        return super().available and self._scale.connected
