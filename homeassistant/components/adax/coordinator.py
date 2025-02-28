"""DataUpdateCoordinator for the Adax component."""

from datetime import timedelta
import logging
from typing import Any

from adax import Adax

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import ACCOUNT_ID, CLOUD, CONNECTION_TYPE

_LOGGER = logging.getLogger(__name__)


class AdaxCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for updating data to and from Adax (cloud)."""

    rooms: list[dict[str, Any]]

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, update_interval: timedelta
    ) -> None:
        """Initialize the Adax coordinator."""
        super().__init__(
            hass, logger=_LOGGER, name="Adax", update_interval=update_interval
        )

        if entry.data.get(CONNECTION_TYPE) == CLOUD:
            self.adax_data_handler = Adax(
                entry.data[ACCOUNT_ID],
                entry.data[CONF_PASSWORD],
                websession=async_get_clientsession(hass),
            )
        else:
            # The API between Cloud and Local are different, therefore a different coordinator implementation is recommended
            # Also, since AdaxLocal integrations are setup with only 1 entity per config entry, also reduces the need for a coordinator
            raise RuntimeError("AdaxCoordinator is not to be used for AdaxLocal")

    def get_room(self, room_id: int) -> dict[str, Any]:
        """Get a specific room from the loaded Adax data."""
        rooms = self.rooms or []
        for room in filter(lambda r: r["id"] == room_id, rooms):
            return room
        return None

    def get_rooms(self) -> list[dict[str, Any]]:
        """Get all rooms for the account."""
        return self.rooms or []

    async def _async_update_data(self) -> list[dict[str, Any]]:
        """Fetch data from the Adax."""
        try:
            self.rooms = await self.adax_data_handler.get_rooms()
        except Exception as err:
            _LOGGER.fatal("Exception when getting data. Err: %s", err)
            raise UpdateFailed(f"Error communicating with API: {err}") from err
        else:
            return self.rooms
