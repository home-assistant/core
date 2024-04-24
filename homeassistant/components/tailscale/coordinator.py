"""DataUpdateCoordinator for the Tailscale integration."""

from __future__ import annotations

from tailscale import Device, Tailscale, TailscaleAuthenticationError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_TAILNET, DOMAIN, LOGGER, SCAN_INTERVAL


class TailscaleDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Device]]):
    """The Tailscale Data Update Coordinator."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the Tailscale coordinator."""
        self.config_entry = entry

        session = async_get_clientsession(hass)
        self.tailscale = Tailscale(
            session=session,
            api_key=entry.data[CONF_API_KEY],
            tailnet=entry.data[CONF_TAILNET],
        )

        super().__init__(hass, LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)

    async def _async_update_data(self) -> dict[str, Device]:
        """Fetch devices from Tailscale."""
        try:
            return await self.tailscale.devices()
        except TailscaleAuthenticationError as err:
            raise ConfigEntryAuthFailed from err
