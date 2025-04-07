"""Base entity for poolsense integration."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN
from .coordinator import PoolSenseDataUpdateCoordinator


class PoolSenseEntity(CoordinatorEntity[PoolSenseDataUpdateCoordinator]):
    """Implements a common class elements representing the PoolSense component."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PoolSenseDataUpdateCoordinator,
        description: EntityDescription,
    ) -> None:
        """Initialize poolsense entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.email}-{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.email)},
            model="PoolSense",
        )
