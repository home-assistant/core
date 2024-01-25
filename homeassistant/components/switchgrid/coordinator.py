import logging
from typing import TypedDict

import aiohttp
import async_timeout

from homeassistant import core
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


class Event(TypedDict):
    eventId: str


class SwitchgridCoordinator(DataUpdateCoordinator[list[Event]]):
    """Coordinator for updating data from the Switchgrid API."""

    def __init__(
        self,
        hass: core.HomeAssistant,
        config_entry: ConfigEntry,
    ) -> None:
        self._config_entry = config_entry
        super().__init__(
            hass,
            _LOGGER,
            name="Switchgrid Events Data",
            update_interval=UPDATE_INTERVAL,
        )

    async def _async_update_data(self):
        try:
            async with async_timeout.timeout(10):
                url = "https://licarth.eu.ngrok.io/api/homeassistant/events"
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as response:
                        response.raise_for_status()
                        response_object = await response.json()
                        return response_object

        except aiohttp.ClientError as error:
            raise UpdateFailed(error) from error

    def next_event(self):
        return self.data
