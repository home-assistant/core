"""Base entity for PlayStation Network Integration."""

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PlaystationNetworkCoordinator


class PlaystationNetworkServiceEntity(CoordinatorEntity[PlaystationNetworkCoordinator]):
    """Common entity class for PlayStationNetwork Service entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator) -> None:
        """Initialize PlayStation Network Service Entity."""
        super().__init__(coordinator)
        self.coordinator = coordinator

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.unique_id)},
            name=coordinator.data.username,
            entry_type=DeviceEntryType.SERVICE,
            manufacturer="Sony Interactive Entertainment",
        )
