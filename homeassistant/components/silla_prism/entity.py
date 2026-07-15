"""Base entity for the Silla Prism integration."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL
from .coordinator import PrismCoordinator


class PrismEntity(CoordinatorEntity[PrismCoordinator]):
    """Base class linking every entity to the single Prism device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: PrismCoordinator, key: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        base_topic = coordinator.base_topic
        self._attr_unique_id = f"{base_topic}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, base_topic)},
            manufacturer=MANUFACTURER,
            model=MODEL,
            name="Silla Prism",
        )
