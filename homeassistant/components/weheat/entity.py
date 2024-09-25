"""Base entity for Weheat."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import WeheatDataUpdateCoordinator


class WeheatEntity(CoordinatorEntity[WeheatDataUpdateCoordinator]):
    """Defines a base Weheat entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: WeheatDataUpdateCoordinator,
    ) -> None:
        """Initialize the Weheat entity."""
        super().__init__(coordinator)

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.heatpump_id)},
            name=coordinator.readable_name,
            manufacturer=MANUFACTURER,
            model=coordinator.model,
        )
