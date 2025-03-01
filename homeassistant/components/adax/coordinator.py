"""DataUpdateCoordinator for the Adax component."""

import logging
from typing import Any

from adax import Adax
from adax_local import Adax as AdaxLocal

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import ACCOUNT_ID, CLOUD, CONNECTION_TYPE, LOCAL, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class AdaxCloudCoordinator(DataUpdateCoordinator[list[dict[str, Any]]]):
    """Coordinator for updating data to and from Adax (cloud)."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the Adax coordinator used for Cloud mode."""
        super().__init__(
            hass,
            config_entry=entry,
            logger=_LOGGER,
            name="AdaxCloud",
            update_interval=SCAN_INTERVAL,
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
        for room in filter(lambda r: r["id"] == room_id, self.data):
            return room
        return None

    async def _async_update_data(self) -> list[dict[str, Any]]:
        """Fetch data from the Adax."""
        return await self.adax_data_handler.get_rooms() or []


class AdaxLocalCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for updating data to and from Adax (local)."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the Adax coordinator used for Local mode."""
        super().__init__(
            hass,
            config_entry=entry,
            logger=_LOGGER,
            name="AdaxLocal",
            update_interval=SCAN_INTERVAL,
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

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the Adax."""
        return await self.adax_data_handler.get_status()
