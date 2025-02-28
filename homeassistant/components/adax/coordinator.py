"""DataUpdateCoordinator for the Adax component."""

from datetime import timedelta
import logging
from typing import Any

from adax import Adax
from adax_local import Adax as AdaxLocal

from homeassistant.core import HomeAssistant
from homeassistant.const import (
    CONF_IP_ADDRESS,
    CONF_PASSWORD,
    CONF_TOKEN,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import ACCOUNT_ID, CONNECTION_TYPE, DOMAIN, LOCAL

_LOGGER = logging.getLogger(__name__)


class AdaxCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for updating data to and from Adax."""

    rooms: dict[str, Any]

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        update_interval: timedelta
    ) -> None:
        """Initialize the Adax coordinator."""
        super().__init__(hass, logger=_LOGGER, name="Adax", update_interval=update_interval)

        if entry.data.get(CONNECTION_TYPE) == LOCAL:
            self.adax_data_handler = AdaxLocal(
                entry.data[CONF_IP_ADDRESS],
                entry.data[CONF_TOKEN],
                websession=async_get_clientsession(hass, verify_ssl=False),
            )
        else:
            self.adax_data_handler = Adax(
                entry.data[ACCOUNT_ID],
                entry.data[CONF_PASSWORD],
                websession=async_get_clientsession(hass),
            )

    def get_room(self, room_id: int) -> dict[str, Any]:
        """Get a specific room from the loaded Adax data."""
        for room in filter(lambda r: r['id'] == room_id, self.get_rooms()):
            _LOGGER.info("Get Room: %s", room)
            return room
        return None

    def get_rooms(self) -> list[dict[str, Any]]:
        """Gets all rooms for the account."""
        return self.rooms or []

    async def _async_update_data(self) -> None:
        """Fetch data from the Adax."""
        try:
            _LOGGER.info("Getting data from Adax")
            self.rooms = await self.adax_data_handler.get_rooms()
        except Exception as err:
            _LOGGER.fatal(
                "Exception when getting data. Err: %s", err
            )
            raise UpdateFailed(f"Error communicating with API: {err}") from err
        else:
            _LOGGER.info("ROOMS: %s", self.rooms)
            return self.rooms
