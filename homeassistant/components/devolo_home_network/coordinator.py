"""Base coordinator."""

from asyncio import Semaphore
from collections.abc import Awaitable, Callable
from datetime import timedelta
from logging import Logger

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator


class DevoloDataUpdateCoordinator[_DataT](DataUpdateCoordinator[_DataT]):
    """Class to manage fetching data from devolo Home Network devices."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: Logger,
        *,
        config_entry: ConfigEntry,
        name: str,
        semaphore: Semaphore,
        update_interval: timedelta,
        update_method: Callable[[], Awaitable[_DataT]],
    ) -> None:
        """Initialize global data updater."""
        super().__init__(
            hass,
            logger,
            config_entry=config_entry,
            name=name,
            update_interval=update_interval,
            update_method=update_method,
        )
        self._semaphore = semaphore

    async def _async_update_data(self) -> _DataT:
        """Fetch the latest data from the source."""
        async with self._semaphore:
            return await super()._async_update_data()
