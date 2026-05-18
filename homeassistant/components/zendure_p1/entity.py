"""Base entity for Zendure Smart Meter P1 integration."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ZendureP1Coordinator


class ZendureP1Entity(CoordinatorEntity[ZendureP1Coordinator]):
    """Defines a base Zendure Smart Meter P1 entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: ZendureP1Coordinator) -> None:
        """Initialize the Zendure Smart Meter P1 entity."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.data.device_id)},
            manufacturer="Zendure",
            name="Smart Meter P1",
        )
