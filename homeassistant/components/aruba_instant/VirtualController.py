import logging

from instantpy import InstantVC

from .const import DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import HomeAssistantType

_LOGGER = logging.getLogger(__name__)


class VirtualController:
    """
    Instantiate an InstantVC object.
    """
    _LOGGER.debug(f"Initializing Aruba Instant Virtual Controller")
    def __init__(self, hass: HomeAssistantType, entry: ConfigEntry):
        self.hass = hass
        self.vc_name = ""
        self.host = entry.data.get("host")
        self.port = entry.data.get("port")
        self._entry = entry
        self._clients = {}
        self._aps = {}
        self._virtual_controller = InstantVC(
            entry.data.get("host"),
            entry.data.get("username"),
            entry.data.get("password"),
            port=entry.data.get("port"),
            ssl_verify=entry.data.get("verify_ssl"),
        )
        self._logged_in = self._virtual_controller.logged_in

    async def async_setup(self) -> [bool, ConnectionError]:
        """Set up an Aruba Instant Virtual Controller."""
        _LOGGER.debug(f"Initial Virtual Controller login.")
        try:
            await self.hass.async_add_executor_job(self._virtual_controller.login)
        except ConnectionError:
            return ConnectionError
        await self.async_update_all()
        return True

    async def async_update_all(self) -> dict:
        """Update Instant VC clients and APs."""
        _LOGGER.debug(f"Updating clients and APs.")
        self._clients = await self.async_update_clients()
        self._aps = await self.async_update_aps()
        return self._clients

    async def async_update_clients(self) -> dict:
        """Update Instant VC clients."""
        updates = await self.hass.async_add_executor_job(
            self._virtual_controller.clients
        )
        return updates

    async def async_update_aps(self) -> dict:
        """Update Instant VC APs."""
        updates = await self.hass.async_add_executor_job(self._virtual_controller.aps)
        return updates

    @property
    def signal_device_update(self) -> str:
        """Event specific per Instant VC entry to signal updates in devices."""
        return f"{DOMAIN}-{self.host}-device-update"

    @property
    def signal_device_new(self) -> str:
        """Event specific per Instant VC entry to signal new device."""
        return f"{DOMAIN}-{self.host}-device-new"

    @property
    def clients(self) -> dict:
        """Return list of connected clients."""
        return self._clients

    @property
    def aps(self) -> dict:
        """Return list of APs."""
        return self._aps

    @property
    def logged_in(self) -> bool:
        """Return logged in status."""
        return self._logged_in

    @property
    def entry_id(self) -> str:
        """Return entity_id for the Virtual Controller."""
        return self._entry.entry_id
