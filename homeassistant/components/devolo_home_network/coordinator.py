"""Base coordinator."""

from asyncio import Semaphore
from collections.abc import Awaitable, Callable
from datetime import timedelta
from logging import Logger

from typing_extensions import TypeVar

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_DataT = TypeVar("_DataT")


class DevoloDataUpdateCoordinator(DataUpdateCoordinator[_DataT]):
    """Class to manage fetching data from devolo Home Network devices."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: Logger,
        *,
        name: str,
        semaphore: Semaphore,
        update_interval: timedelta | None = None,
        update_method: Callable[[], Awaitable[_DataT]] | None = None,
    ) -> None:
        """Initialize global data updater."""
        super().__init__(
            hass,
            logger,
            name=name,
            update_interval=update_interval,
            update_method=update_method,
        )
        self._semaphore = semaphore

    async def _async_update_data(self) -> _DataT:
        """Fetch the latest data from the source."""
        if self.update_method is None:
            raise NotImplementedError("Update method not implemented")
        async with self._semaphore:
            return await self.update_method()
