"""Coordinate data for powerview devices."""
from __future__ import annotations

from datetime import timedelta
import logging

from aiopvapi.helpers.constants import ATTR_ID
from aiopvapi.shades import Shades
import async_timeout

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import SHADE_DATA

_LOGGER = logging.getLogger(__name__)


class PowerviewShadeUpdateCoordinator(DataUpdateCoordinator):
    """DataUpdateCoordinator to gather data from a powerview hub."""

    def __init__(
        self,
        hass: HomeAssistant,
        shades: Shades,
        hub_address: str,
    ) -> None:
        """Initialize DataUpdateCoordinator to gather data for specific SmartPlug."""
        self.shades = shades
        super().__init__(
            hass,
            _LOGGER,
            name=f"powerview hub {hub_address}",
            update_interval=timedelta(seconds=60),
        )

    async def _async_update_data(self) -> None:
        """Fetch data from shade endpoint."""
        async with async_timeout.timeout(10):
            shade_entries = await self.shades.get_resources()
        if not shade_entries:
            raise UpdateFailed("Failed to fetch new shade data")
        old = self.data or {}
        new = async_map_data_by_id(shade_entries[SHADE_DATA])
        for shade_id, new_data in new.items():
            if shade_id in old:
                old[shade_id].update(new_data)
            else:
                old[shade_id] = new_data


@callback
def async_map_data_by_id(data):
    """Return a dict with the key being the id for a list of entries."""
    return {entry[ATTR_ID]: entry for entry in data}
