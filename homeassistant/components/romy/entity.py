"""Base entity for ROMY."""

from romy import RomyRobot

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN

class RomyEntity(CoordinatorEntity[RomyVacuumCoordinator]):
    """Base ROMY entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: RomyVacuumCoordinator) -> None:
        """Initialize ROMY entity."""
        super().__init__(coordinator)
        self.romy = coordinator.romy
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.romy.unique_id)},
            manufacturer="ROMY",
            name=self.romy.name,
            model=self.romy.model,
        )
