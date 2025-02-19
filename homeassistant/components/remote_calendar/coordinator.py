"""Data UpdateCoordinator for the Remote Calendar integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(days=1)

type RemoteCalendarConfigEntry = ConfigEntry[RemoteCalendarDataUpdateCoordinator]


class RemoteCalendarDataUpdateCoordinator(DataUpdateCoordinator[str]):
    """Class to manage fetching calendar data."""

    config_entry: RemoteCalendarConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: RemoteCalendarConfigEntry,
    ) -> None:
        """Initialize data updater."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
            always_update=True,
        )
        self._etag = None
        self._client = get_async_client(hass)
        self._url = config_entry.data["url"]

    async def _async_update_data(self) -> str:
        """Update data from the url."""
        _LOGGER.debug("Fetching data from %s", self._url)
        headers: dict = {}
        res = await self._client.get(self._url, headers=headers)
        res.raise_for_status()
        return res.text
