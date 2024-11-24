"""Data handler for Adax wifi-enabled home heaters."""

from typing import Any

from adax import Adax
from adax_local import Adax as AdaxLocal

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import ACCOUNT_ID, CONNECTION_TYPE, LOCAL


class AdaxDataHandler:
    """Representation of a heater data handler."""

    def __init__(self, entry: ConfigEntry, hass: HomeAssistant) -> None:
        """Initialize the data handler."""
        self._is_local = False
        if entry.data.get(CONNECTION_TYPE) == LOCAL:
            self._is_local = True
            self._adax = AdaxLocal(
                entry.data[CONF_IP_ADDRESS],
                entry.data[CONF_TOKEN],
                websession=async_get_clientsession(hass, verify_ssl=False),
            )
        else:
            self._adax = Adax(
                entry.data[ACCOUNT_ID],
                entry.data[CONF_PASSWORD],
                websession=async_get_clientsession(hass),
            )

        self._rooms = None

    async def async_update(self) -> Any | None:
        """Get the latest data."""
        if self._is_local is False:
            self._rooms = await self._adax.get_rooms()
        else:
            return None
        return self._rooms

    def get_room(self, room_id: Any) -> Any | None:
        """Get room by id."""
        if self._rooms is None:
            return None
        for room in self._rooms:
            if room["id"] == room_id:
                return room
        return None

    def get_rooms(self) -> Any | None:
        """Get all rooms."""
        return self._rooms

    def get_interface(self) -> Adax | AdaxLocal:
        """Get data handler."""
        return self._adax
