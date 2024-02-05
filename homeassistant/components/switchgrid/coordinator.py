import logging

import aiohttp
import async_timeout
from switchgrid_python_client import SwitchgridData

from homeassistant import core
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
import homeassistant.util.dt as dt_util

from .const import UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the calendar platform for entity."""
    coordinator: SwitchgridCoordinator = SwitchgridCoordinator(hass, config_entry)
    async_add_entities([SwitchgridCoordinator(coordinator, config_entry)])


class SwitchgridCoordinator(DataUpdateCoordinator[SwitchgridData]):
    """Coordinator for updating data from the Switchgrid API."""

    def __init__(
        self,
        hass: core.HomeAssistant,
        data: SwitchgridData,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="Switchgrid Events Coordinator",
            update_interval=UPDATE_INTERVAL,
        )
        self._data = data

    async def _async_update_data(self):
        try:
            async with async_timeout.timeout(10):
                await self._data.update()
                return self._data.data
        except aiohttp.ClientError as error:
            raise UpdateFailed(error) from error

    def next_event(self):
        now = dt_util.now()
        return next(
            filter(
                lambda event: event.startUtc > now,
                self._data.data.events,
            ),
            None,
        )
