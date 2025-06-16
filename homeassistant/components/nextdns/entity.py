"""Define NextDNS entities."""

from dataclasses import dataclass

from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import CoordinatorDataT, NextDnsUpdateCoordinator


@dataclass(frozen=True, kw_only=True)
class NextDnsEntityDescription(EntityDescription):
    """NextDNS entity description."""


class NextDnsEntity(CoordinatorEntity[NextDnsUpdateCoordinator[CoordinatorDataT]]):
    """Define NextDNS entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: NextDnsUpdateCoordinator[CoordinatorDataT],
        description: NextDnsEntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = f"{coordinator.profile_id}_{description.key}"
        self.entity_description = description
