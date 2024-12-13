"""Base entity for Playstation Network Integration."""

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PlaystationNetworkConfigEntry, PlaystationNetworkCoordinator


class PlaystationNetworkEntity(CoordinatorEntity[PlaystationNetworkCoordinator]):
    """Common entity class for all Playstation Network entities."""

    config_entry: PlaystationNetworkConfigEntry

    def __init__(self, coordinator: PlaystationNetworkCoordinator) -> None:
        """Initialize PSN Entity."""
        super().__init__(coordinator)

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.user.account_id)},
            name=self.coordinator.user.online_id,
            manufacturer="Sony Interactive Entertainment",
            model="PlayStation Network",
            entry_type=DeviceEntryType.SERVICE,
        )
