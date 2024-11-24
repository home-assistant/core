"""Data handler for Adax wifi-enabled home heaters."""

from typing import Any

from adax import Adax
from adax_local import Adax as AdaxLocal

from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD, CONF_TOKEN
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import ACCOUNT_ID, CONNECTION_TYPE, LOCAL


class AdaxDataHandler:
    """Representation of a heater data handler."""

    def __init__(self, entry, hass) -> None:
        """Initialize the data handler."""
        if entry.data.get(CONNECTION_TYPE) == LOCAL:
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

    async def async_update(self) -> Any:
        """Get the latest data."""
        self._rooms = await self._adax.get_rooms()
        return self._rooms

    def get_room(self, room_id) -> Any:
        """Get room by id."""
        if self._rooms is None:
            return None
        for room in self._rooms:
            if room["id"] == room_id:
                return room
        return None

    def get_rooms(self) -> Any:
        """Get all rooms."""
        return self._rooms

    def get_data_handler(self) -> Adax | AdaxLocal:
        """Get data handler."""
        return self._adax
