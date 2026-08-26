"""Shared entity base: device_info and the coordinator plumbing."""

from dataclasses import dataclass
from typing import override

from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import SofarDataUpdateCoordinator, SofarRuntimeData


@dataclass(frozen=True, kw_only=True)
class SofarEntityDescription(EntityDescription):
    """Which Component on the device an entity reads or acts through."""

    component: str  # attribute name on SofarInverter, e.g. 'grid', 'pv_1_2'


class SofarEntity(CoordinatorEntity[SofarDataUpdateCoordinator]):
    """Base for every Sofar entity; one physical inverter per config entry."""

    _attr_has_entity_name = True
    entity_description: SofarEntityDescription

    def __init__(
        self,
        runtime_data: SofarRuntimeData,
        entity_description: SofarEntityDescription,
    ) -> None:
        """Initialize the entity, bound to whichever coordinator serves it."""
        super().__init__(runtime_data.coordinator_for(entity_description.component))
        self.entity_description = entity_description
        serial = self.coordinator.device.serial_number
        assert serial is not None
        self._attr_unique_id = f"{serial}_{entity_description.key}"
        self._attr_device_info = self.coordinator.device_info

    @property
    @override
    def available(self) -> bool:
        """Whether this entity's component answered the most recent poll."""
        if not super().available:
            return False
        report = self.coordinator.data
        return report is None or self.entity_description.component not in report.failed
