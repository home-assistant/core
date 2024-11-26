"""Base entity for Playstation Network Integration."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PlaystationNetworkCoordinator


class PlaystationNetworkEntity(CoordinatorEntity[PlaystationNetworkCoordinator]):
    """Common entity class for all Playstation Network entities."""

    def __init__(self, coordinator) -> None:
        """Initialize PSN Entity."""
        super().__init__(coordinator)
        self.coordinator = coordinator

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.user.account_id)},
            name=self.coordinator.user.online_id,
            manufacturer="Sony Interactive Entertainment",
            model="PlayStation Network",
        )
