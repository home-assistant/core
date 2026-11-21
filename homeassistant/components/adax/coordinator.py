"""DataUpdateCoordinator for the Adax component."""

from datetime import datetime
import logging
from typing import Any, cast, override

from adax import Adax
from adax_local import Adax as AdaxLocal

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import ACCOUNT_ID, SCAN_INTERVAL, STALE_DATA_TIMEOUT

_LOGGER = logging.getLogger(__name__)


type AdaxConfigEntry = ConfigEntry[AdaxCloudCoordinator | AdaxLocalCoordinator]


class AdaxCloudCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Coordinator for updating data to and from Adax (cloud)."""

    config_entry: AdaxConfigEntry

    def __init__(self, hass: HomeAssistant, entry: AdaxConfigEntry) -> None:
        """Initialize the Adax coordinator used for Cloud mode."""
        super().__init__(
            hass,
            config_entry=entry,
            logger=_LOGGER,
            name="AdaxCloud",
            update_interval=SCAN_INTERVAL,
        )

        self.adax_data_handler = self._create_client()
        self._last_rooms: list[dict[str, Any]] | None = None
        self._last_new_data: datetime = dt_util.utcnow()

    def _create_client(self) -> Adax:
        """Create a client for the Adax cloud API."""
        return Adax(
            self.config_entry.data[ACCOUNT_ID],
            self.config_entry.data[CONF_PASSWORD],
            websession=async_get_clientsession(self.hass),
        )

    @override
    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        """Fetch data from the Adax."""
        try:
            if hasattr(self.adax_data_handler, "fetch_rooms_info"):
                rooms = await self.adax_data_handler.fetch_rooms_info() or []
                _LOGGER.debug("fetch_rooms_info returned: %s", rooms)
                new_data = bool(rooms)
            else:
                _LOGGER.debug("fetch_rooms_info method not available, using get_rooms")
                rooms = []
                new_data = False

            if not rooms:
                _LOGGER.debug(
                    "No rooms from fetch_rooms_info, trying get_rooms as fallback"
                )
                rooms = await self.adax_data_handler.get_rooms() or []
                _LOGGER.debug("get_rooms fallback returned: %s", rooms)
                # The client only builds a new list when it got a response,
                # and silently returns its old list when it did not.
                new_data = rooms is not self._last_rooms

            if not rooms:
                raise UpdateFailed("No rooms available from Adax API")

        except OSError as e:
            raise UpdateFailed(f"Error communicating with API: {e}") from e

        now = dt_util.utcnow()
        if new_data:
            self._last_rooms = rooms
            self._last_new_data = now
        elif now - self._last_new_data >= STALE_DATA_TIMEOUT:
            # Start again with a new client, which logs in again.
            self.adax_data_handler = self._create_client()
            self._last_rooms = None
            self._last_new_data = now
            raise UpdateFailed("No new data from the Adax API")

        for room in rooms:
            room["energyWh"] = int(room.get("energyWh", 0))

        return {r["id"]: r for r in rooms}


class AdaxLocalCoordinator(DataUpdateCoordinator[dict[str, Any] | None]):
    """Coordinator for updating data to and from Adax (local)."""

    def __init__(self, hass: HomeAssistant, entry: AdaxConfigEntry) -> None:
        """Initialize the Adax coordinator used for Local mode."""
        super().__init__(
            hass,
            config_entry=entry,
            logger=_LOGGER,
            name="AdaxLocal",
            update_interval=SCAN_INTERVAL,
        )

        self.adax_data_handler = AdaxLocal(
            entry.data[CONF_IP_ADDRESS],
            entry.data[CONF_TOKEN],
            websession=async_get_clientsession(hass, verify_ssl=False),
        )

    @override
    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the Adax."""
        if result := await self.adax_data_handler.get_status():
            return cast(dict[str, Any], result)
        raise UpdateFailed("Got invalid status from device")
