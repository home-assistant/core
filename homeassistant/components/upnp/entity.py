"""Entity for UPnP/IGD."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import UpnpDataUpdateCoordinator


@dataclass(frozen=True)
class UpnpEntityDescription(EntityDescription):
    """UPnP entity description."""

    unique_id: str | None = None
    value_key: str | None = None

    def __post_init__(self):
        """Post initialize."""
        object.__setattr__(self, "value_key", self.value_key or self.key)


class UpnpEntity(CoordinatorEntity[UpnpDataUpdateCoordinator]):
    """Base class for UPnP/IGD entities."""

    entity_description: UpnpEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: UpnpDataUpdateCoordinator,
        entity_description: UpnpEntityDescription,
    ) -> None:
        """Initialize the base entities."""
        super().__init__(coordinator)
        self._device = coordinator.device
        self.entity_description = entity_description
        self._attr_unique_id = f"{coordinator.device.original_udn}_{entity_description.unique_id or entity_description.key}"
        self._attr_device_info = DeviceInfo(
            connections=coordinator.device_entry.connections,
            name=coordinator.device_entry.name,
            manufacturer=coordinator.device_entry.manufacturer,
            model=coordinator.device_entry.model,
            configuration_url=coordinator.device_entry.configuration_url,
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and (
            self.coordinator.data.get(self.entity_description.key) is not None
        )
