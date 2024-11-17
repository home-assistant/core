"""Base entity for Playstation Network Integration."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import PlaystationNetworkConfigEntry
from .const import DOMAIN
from .coordinator import PlaystationNetworkCoordinator


async def async_setup_entry(
    hass: HomeAssistant, config_entry: PlaystationNetworkConfigEntry
):
    """Add sensors for passed config_entry in HA."""
    # coordinator = config_entry.runtime_data.coordinator


class PlaystationNetworkEntity(CoordinatorEntity[PlaystationNetworkCoordinator]):
    """Common entity class for all Playstation Network entities."""

    def __init__(self, coordinator) -> None:
        """Initialize PSN Entity."""
        super().__init__(coordinator)
        self.coordinator = coordinator

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        username: str = "PSN"
        if len(self.coordinator.data.username) > 0:
            username = str(self.coordinator.data.username)

        return DeviceInfo(
            identifiers={(DOMAIN, username)},
            name=username,
            manufacturer="Sony",
            model="Playstation Network",
            configuration_url="https://ca.account.sony.com/api/v1/ssocookie",
        )

    @property
    def should_poll(self) -> bool:
        """Should the individual entity poll."""
        return False
