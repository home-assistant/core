"""What every KACO entity shares."""

from dataclasses import dataclass
from typing import override

from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import KacoDataUpdateCoordinator


@dataclass(frozen=True, kw_only=True)
class KacoEntityDescription(EntityDescription):
    """Which component on the inverter an entity reads through."""

    component: str  # attribute name on KacoInverter, e.g. 'inverter'


class KacoEntity(CoordinatorEntity[KacoDataUpdateCoordinator]):
    """An entity backed by one component of the inverter.

    Components are polled independently, so an entity is unavailable when its
    own component failed to read, not when any of them did.
    """

    _attr_has_entity_name = True
    entity_description: KacoEntityDescription

    def __init__(
        self,
        coordinator: KacoDataUpdateCoordinator,
        entity_description: KacoEntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = entity_description

        info = coordinator.device.info
        assert info is not None
        self._attr_unique_id = f"{info.serial_number}_{entity_description.key}"
        self._attr_device_info = coordinator.device_info

    @property
    @override
    def available(self) -> bool:
        """Whether this entity's own component answered the last poll."""
        return (
            super().available
            and self.entity_description.component in self.coordinator.data.updated
        )
