"""Instant Virtual Controller abstraction class for HA"""

import logging

from instantpy import InstantVC

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import HomeAssistantType

from .const import DOMAIN, TRACKED_DEVICES

_LOGGER = logging.getLogger(__name__)


class VirtualController:
    """
    Instantiate an InstantVC object.
    """
    _LOGGER.debug("Initializing Aruba Instant Virtual Controller")
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
        selected_clients = entry.data.get('clients')
        try:
            for client in selected_clients:
                hass.data[DOMAIN][TRACKED_DEVICES][self.entry_id].add(client)
            # entry.data['clients'].clear()
        except TypeError:
            _LOGGER.debug("No clients selected to track.")

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
