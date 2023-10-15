"""Base class for the La Marzocco entities."""

from dataclasses import dataclass

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo, format_mac
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .acaiaclient import AcaiaClient
from .const import DOMAIN


@dataclass
class AcaiaEntityDescriptionMixin:
    """Mixin for all LM entities."""


@dataclass
class AcaiaEntityDescription(EntityDescription, AcaiaEntityDescriptionMixin):
    """Description for all LM entities."""


@dataclass
class AcaiaEntity(CoordinatorEntity):
    """Common elements for all entities."""

    entity_description: AcaiaEntityDescription

    def __init__(self, coordinator, entity_description) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._scale: AcaiaClient = coordinator.acaia_client
        self._attr_unique_id = (
            f"{format_mac(self._scale.mac)}_{self.entity_description.key}"
        )
        self._attr_has_entity_name = True

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._scale.mac)},
            name=self._scale.name,
            manufacturer="acaia",
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()
