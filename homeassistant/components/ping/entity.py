"""Base entity for the Ping component."""
from homeassistant.core import DOMAIN
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import PingUpdateCoordinator


class PingEntity(CoordinatorEntity[PingUpdateCoordinator]):
    """Represents a Ping base entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PingUpdateCoordinator,
        unique_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        self._attr_unique_id = unique_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.data.ip_address)},
            manufacturer="Ping",
        )
