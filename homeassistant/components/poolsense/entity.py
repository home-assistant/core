"""Base entity for poolsense integration."""

from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION
from .coordinator import PoolSenseDataUpdateCoordinator


class PoolSenseEntity(CoordinatorEntity[PoolSenseDataUpdateCoordinator]):
    """Implements a common class elements representing the PoolSense component."""

    _attr_attribution = ATTRIBUTION

    def __init__(
        self,
        coordinator: PoolSenseDataUpdateCoordinator,
        email: str,
        description: EntityDescription,
    ) -> None:
        """Initialize poolsense sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_name = f"PoolSense {description.name}"
        self._attr_unique_id = f"{email}-{description.key}"
