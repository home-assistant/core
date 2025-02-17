"""Data UpdateCoordinator for the Husqvarna Automower integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(days=1)


class RemoteCalendarDataUpdateCoordinator(DataUpdateCoordinator[str]):
    """Class to manage fetching Husqvarna data."""

    def __init__(self, hass: HomeAssistant, entry_data) -> None:
        """Initialize data updater."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self._etag = None
        self._client = get_async_client(hass)
        # self._url = "https://calendar.google.com/calendar/ical/p07n98go11onamd08d0kmq6jhs%40group.calendar.google.com/public/basic.ics"
        self._url = entry_data["url"]

    async def _async_update_data(self) -> str:
        """Subscribe for websocket and poll data from the API."""
        headers: dict = {}
        if self._etag:
            headers["If-None-Match"] = self._etag
        res = await self._client.get(self._url, headers=headers)
        # if res.status_code == 304:  # Not modified
        #     return None
        res.raise_for_status()
        self._etag = res.headers.get("ETag")
        return res.text
