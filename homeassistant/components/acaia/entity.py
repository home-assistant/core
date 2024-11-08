"""Base class for Acaia entities."""

from dataclasses import dataclass

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
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
        self._attr_unique_id = f"{self._scale.mac}_{entity_description.key}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._scale.mac)},
            manufacturer="Acaia",
            model=(
                coordinator.config_entry.title.split("-")[0].capitalize()
                if "-" in coordinator.config_entry.title
                else None
            ),
            suggested_area="Kitchen",
        )

    @property
    def available(self) -> bool:
        """Returns whether entity is available."""
        return super().available and self._scale.connected

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._scale = self.coordinator.scale
        self.async_write_ha_state()
