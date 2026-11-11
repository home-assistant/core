"""Base entity for Zehnder ComfoConnect PRO gateways."""

from dataclasses import dataclass
from typing import override

from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import ComfoConnectProDataUpdateCoordinator


@dataclass(frozen=True, kw_only=True)
class ComfoConnectProEntityDescription(EntityDescription):
    """Describe a ComfoConnect PRO entity."""

    # `component` names the attribute of ComfoConnectPro that holds the data.
    component: str


class ComfoConnectProEntity(CoordinatorEntity[ComfoConnectProDataUpdateCoordinator]):
    """Defines a base ComfoConnect PRO entity."""

    _attr_has_entity_name = True
    entity_description: ComfoConnectProEntityDescription

    def __init__(
        self,
        coordinator: ComfoConnectProDataUpdateCoordinator,
        entity_description: ComfoConnectProEntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_{entity_description.key}"
        )
        self._attr_device_info = coordinator.device_info

    @property
    @override
    def available(self) -> bool:
        """Whether this entity's component answered the most recent poll."""
        if not super().available:
            return False
        return self.entity_description.component not in self.coordinator.data.failed
