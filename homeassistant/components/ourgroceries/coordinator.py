"""The OurGroceries coordinator."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

from ourgroceries import OurGroceries

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

SCAN_INTERVAL = 60

_LOGGER = logging.getLogger(__name__)


class OurGroceriesDataUpdateCoordinator(DataUpdateCoordinator[dict[str, dict]]):
    """Class to manage fetching OurGroceries data."""

    config_entry: ConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: ConfigEntry, og: OurGroceries
    ) -> None:
        """Initialize global OurGroceries data updater."""
        self.og = og
        self.lists: list[dict] = []
        self._cache: dict[str, dict] = {}
        interval = timedelta(seconds=SCAN_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=interval,
        )

    async def _update_list(self, list_id: str, version_id: str) -> None:
        old_version = self._cache.get(list_id, {}).get("list", {}).get("versionId", "")
        if old_version == version_id:
            return
        self._cache[list_id] = await self.og.get_list_items(list_id=list_id)

    async def _async_update_data(self) -> dict[str, dict]:
        """Fetch data from OurGroceries."""
        self.lists = (await self.og.get_my_lists())["shoppingLists"]
        await asyncio.gather(
            *[self._update_list(sl["id"], sl["versionId"]) for sl in self.lists]
        )
        return self._cache
