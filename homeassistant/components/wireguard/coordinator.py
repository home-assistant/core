"""DataUpdateCoordinator for WIreGUard integration."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import WireGuardAPI, WireGuardError, WireGuardPeer, peer_from_data
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, LOGGER


class WireGuardUpdateCoordinator(DataUpdateCoordinator):
    """A WireGuard Data Update Coordinator."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the WireGuard API."""
        self.entry = entry
        self.wireguard = WireGuardAPI(host=entry.data[CONF_HOST])

        super().__init__(
            hass, LOGGER, name=DOMAIN, update_interval=DEFAULT_SCAN_INTERVAL
        )

    async def _async_update_data(self) -> list[WireGuardPeer]:
        """Get peers from the WireGuardAPI."""
        try:
            status = await self.hass.async_add_executor_job(self.wireguard.get_status)
            return [peer_from_data(name, data) for name, data in status.items()]
        except WireGuardError as err:
            raise UpdateFailed("Could not get peers") from err
