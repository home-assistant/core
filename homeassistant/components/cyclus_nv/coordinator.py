"""Data update coordinator for Cyclus NV."""

from __future__ import annotations

from cyclus.cyclus import CyclusClient
from cyclus.exceptions import CyclusError
from cyclus.models import CalendarEvent

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import CONF_BAG_ID, DOMAIN, LOGGER, SCAN_INTERVAL

type CyclusNVConfigEntry = ConfigEntry[CyclusNVDataUpdateCoordinator]


class CyclusNVDataUpdateCoordinator(DataUpdateCoordinator[list[CalendarEvent]]):
    """Class to manage fetching Cyclus NV data."""

    def __init__(self, hass: HomeAssistant, entry: CyclusNVConfigEntry) -> None:
        """Initialize Cyclus NV data update coordinator."""
        self.client = CyclusClient(
            bag_id=entry.data[CONF_BAG_ID],
            session=async_get_clientsession(hass),
        )
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
            config_entry=entry,
        )

    async def _async_update_data(self) -> list[CalendarEvent]:
        """Fetch Cyclus NV data."""
        try:
            return await self.client.get_calendar_events(dt_util.now().year)
        except CyclusError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
            ) from err
