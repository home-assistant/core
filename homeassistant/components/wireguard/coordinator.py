"""DataUpdateCoordinator for WIreGUard integration."""
from aiohttp import ClientSession
from ha_wireguard_api import WireguardApiClient
from ha_wireguard_api.exceptions import (
    WireGuardInvalidJson,
    WireGuardResponseError,
    WireGuardTimeoutError,
)
from ha_wireguard_api.model import WireGuardPeer

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, LOGGER


class WireGuardUpdateCoordinator(DataUpdateCoordinator):
    """A WireGuard Data Update Coordinator."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the WireGuard API."""
        self.entry = entry
        session: ClientSession = async_get_clientsession(hass)
        self.wireguard = WireguardApiClient(host=entry.data[CONF_HOST], session=session)
        self.data: dict[str, WireGuardPeer]

        super().__init__(
            hass, LOGGER, name=DOMAIN, update_interval=DEFAULT_SCAN_INTERVAL
        )

    async def _async_update_data(self) -> dict[str, WireGuardPeer]:
        """Get peers from the WireGuardAPI."""
        try:
            peers: list[WireGuardPeer] = await self.wireguard.get_peers()
        except (
            WireGuardInvalidJson,
            WireGuardResponseError,
            WireGuardTimeoutError,
        ) as err:
            raise UpdateFailed(err) from err
        data: dict[str, WireGuardPeer] = {}
        data.update({peer.name: peer for peer in peers})
        return data
