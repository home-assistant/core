"""Data update coordinator for SimpliSafe."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import LOGGER

if TYPE_CHECKING:
    from . import SimpliSafe

DEFAULT_SCAN_INTERVAL = timedelta(seconds=30)


class SimpliSafeDataUpdateCoordinator(DataUpdateCoordinator[None]):
    """Class to manage fetching SimpliSafe data."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        *,
        name: str,
        simplisafe: SimpliSafe,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name=name,
            config_entry=config_entry,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self._simplisafe = simplisafe

    async def _async_update_data(self) -> None:
        """Fetch data from SimpliSafe."""
        await self._simplisafe.async_update()
