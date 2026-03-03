"""Coordinator for the mütesync integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import mutesync

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, UPDATE_INTERVAL_IN_MEETING, UPDATE_INTERVAL_NOT_IN_MEETING

_LOGGER = logging.getLogger(__name__)


class MutesyncUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for the mütesync integration."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=UPDATE_INTERVAL_NOT_IN_MEETING,
        )
        self._client = mutesync.PyMutesync(
            entry.data["token"],
            entry.data["host"],
            async_get_clientsession(hass),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Get data from the mütesync client."""
        async with asyncio.timeout(2.5):
            state = await self._client.get_state()

            if state["muted"] is None or state["in_meeting"] is None:
                raise UpdateFailed("Got invalid response")

            if state["in_meeting"]:
                self.update_interval = UPDATE_INTERVAL_IN_MEETING
            else:
                self.update_interval = UPDATE_INTERVAL_NOT_IN_MEETING

            return state
