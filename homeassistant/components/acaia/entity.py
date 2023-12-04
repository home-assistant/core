"""Base class for the La Marzocco entities."""

from dataclasses import dataclass

from homeassistant.helpers.device_registry import DeviceInfo, format_mac
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .acaiaclient import AcaiaClient
from .const import DOMAIN
from .coordinator import AcaiaApiCoordinator


@dataclass
class AcaiaEntityDescription(EntityDescription):
    """Description for all LM entities."""


@dataclass
class AcaiaEntity(CoordinatorEntity[AcaiaApiCoordinator]):
    """Common elements for all entities."""

    entity_description: AcaiaEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AcaiaApiCoordinator,
        entity_description: AcaiaEntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._scale: AcaiaClient = coordinator.data
        self._attr_unique_id = (
            f"{format_mac(self._scale.mac)}_{self.entity_description.key}"
        )

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._scale.mac)},
            name=self._scale.name,
            manufacturer="acaia",
        )
