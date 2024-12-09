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
            return

        self._adax = Adax(
            entry.data[ACCOUNT_ID],
            entry.data[CONF_PASSWORD],
            websession=async_get_clientsession(hass),
        )

        self._rooms = None

    async def async_update(self) -> list[dict] | None:
        """Get the latest data."""
        if self._is_local is True:
            return
        self._rooms = await self._adax.get_rooms()
        return self._rooms

    def get_interface(self) -> Adax | AdaxLocal:
        """Get data handler."""
        return self._adax
