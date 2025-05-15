"""Support for IQVIA."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from datetime import timedelta
from typing import Any

from pyiqvia import Client
from pyiqvia.errors import IQVIAError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import LOGGER

DEFAULT_SCAN_INTERVAL = timedelta(minutes=30)


class IqviaUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Custom DataUpdateCoordinator for IQVIA."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        client: Client,
        config_entry: ConfigEntry,
        name: str,
        update_method: Callable[[], Coroutine[Any, Any, dict[str, Any]]],
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name=name,
            config_entry=config_entry,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self._client = client
        self._update_method = update_method

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the API."""
        try:
            return await self._update_method()
        except IQVIAError as err:
            raise UpdateFailed from err
