"""Base entity for ROMY."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import RomyVacuumCoordinator


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
