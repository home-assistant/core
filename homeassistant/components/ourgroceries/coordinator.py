"""The OurGroceries coordinator."""
from __future__ import annotations

from datetime import timedelta
import logging

from ourgroceries import OurGroceries

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

SCAN_INTERVAL = 60

_LOGGER = logging.getLogger(__name__)


class OurGroceriesDataUpdateCoordinator(DataUpdateCoordinator[dict[str, dict]]):
    """Class to manage fetching OurGroceries data."""

    def __init__(
        self, hass: HomeAssistant, og: OurGroceries, lists: list[dict]
    ) -> None:
        """Initialize global OurGroceries data updater."""
        self.og = og
        self.lists = lists
        interval = timedelta(seconds=SCAN_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=interval,
        )

    async def _async_update_data(self) -> dict[str, dict]:
        """Fetch data from OurGroceries."""
        return {
            sl["id"]: (await self.og.get_list_items(list_id=sl["id"]))
            for sl in self.lists
        }
