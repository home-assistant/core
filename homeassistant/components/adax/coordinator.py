"""DataUpdateCoordinator for the Adax component."""

from datetime import timedelta
import logging
from typing import Any

from adax import Adax
from adax_local import Adax as AdaxLocal

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import ACCOUNT_ID, CLOUD, CONNECTION_TYPE, LOCAL

_LOGGER = logging.getLogger(__name__)


class AdaxCloudCoordinator(DataUpdateCoordinator[list[dict[str, Any]]]):
    """Coordinator for updating data to and from Adax (cloud)."""

    rooms: list[dict[str, Any]]

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, update_interval: timedelta
    ) -> None:
        """Initialize the Adax coordinator used for Cloud mode."""
        super().__init__(
            hass, logger=_LOGGER, name="AdaxCloud", update_interval=update_interval
        )

        if entry.data.get(CONNECTION_TYPE) != CLOUD:
            raise RuntimeError(
                "AdaxCloudCoordinator can only be used for Cloud connections"
            )

        self.adax_data_handler = Adax(
            entry.data[ACCOUNT_ID],
            entry.data[CONF_PASSWORD],
            websession=async_get_clientsession(hass),
        )

    def get_room(self, room_id: int) -> dict[str, Any] | None:
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
            _LOGGER.error("Exception when getting data. Err: %s", err)
            raise UpdateFailed(f"Error communicating with API: {err}") from err
        else:
            return self.rooms


class AdaxLocalCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for updating data to and from Adax (local)."""

    status: dict[str, Any] | None

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, update_interval: timedelta
    ) -> None:
        """Initialize the Adax coordinator used for Local mode."""
        super().__init__(
            hass, logger=_LOGGER, name="AdaxLocal", update_interval=update_interval
        )

        if entry.data.get(CONNECTION_TYPE) != LOCAL:
            raise RuntimeError(
                "AdaxLocalCoordinator can only be used for Local connections"
            )

        self.adax_data_handler = AdaxLocal(
            entry.data[CONF_IP_ADDRESS],
            entry.data[CONF_TOKEN],
            websession=async_get_clientsession(hass, verify_ssl=False),
        )

    def get_status(self) -> dict[str, Any] | None:
        """Get status for the Adax device."""
        return self.status

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the Adax."""
        try:
            self.status = await self.adax_data_handler.get_status()
        except Exception as err:
            _LOGGER.error("Exception when getting data. Err: %s", err)
            raise UpdateFailed(f"Error communicating with API: {err}") from err
        else:
            return self.status
