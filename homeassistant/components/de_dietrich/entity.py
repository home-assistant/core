"""Base entity for De Dietrich devices."""

from dataclasses import dataclass
from typing import override

from homeassistant.helpers.device_registry import ChildDeviceInfo, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import CHILD_COMPONENT_DEVICE_NAMES, DeDietrichDataUpdateCoordinator


@dataclass(frozen=True, kw_only=True)
class DeDietrichEntityDescription(EntityDescription):
    """Describe a De Dietrich entity."""

    component: str


class DeDietrichEntity(CoordinatorEntity[DeDietrichDataUpdateCoordinator]):
    """Defines a base De Dietrich entity."""

    _attr_has_entity_name = True
    entity_description: DeDietrichEntityDescription

    def __init__(
        self,
        coordinator: DeDietrichDataUpdateCoordinator,
        entity_description: DeDietrichEntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_{entity_description.key}"
        )

    @property
    @override
    def device_info(self) -> DeviceInfo | ChildDeviceInfo:
        """Route to the child device for this bundle's component when it reports live readings, otherwise fall back to the boiler device.

        Presence is cached by the dependency, so a transient poll failure does not detach the entity from its child device.
        """
        coordinator = self.coordinator
        component = self.entity_description.component
        if component in CHILD_COMPONENT_DEVICE_NAMES:
            child = coordinator.child_device_info(component)
            if child is not None:
                return child
        return coordinator.device_info

    @property
    @override
    def available(self) -> bool:
        """Whether this entity's component answered the most recent poll."""
        return (
            super().available
            and self.entity_description.component not in self.coordinator.data.failed
        )
