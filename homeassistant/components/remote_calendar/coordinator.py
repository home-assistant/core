"""Data UpdateCoordinator for the Husqvarna Automower integration."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import timedelta
import logging
from typing import TYPE_CHECKING

from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

# from ical.calendar import Calendar
# from ical.calendar_stream import IcsCalendarStream
# from ical.event import Event
from .const import DOMAIN


_LOGGER = logging.getLogger(__name__)
MAX_WS_RECONNECT_TIME = 600
SCAN_INTERVAL = timedelta(minutes=8)
DEFAULT_RECONNECT_TIME = 2  # Define a default reconnect time


class RemoteCalendarDataUpdateCoordinator(DataUpdateCoordinator):
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

    async def _async_update_data(self) -> dict:
        """Subscribe for websocket and poll data from the API."""
        headers = {}
        if self._etag:
            headers["If-None-Match"] = self._etag
        res = await self._client.get(self._url, headers=headers)
        if res.status_code == 304:  # Not modified
            return
        res.raise_for_status()
        self._etag = res.headers.get("ETag")
        return res.text
