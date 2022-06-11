"""Coordinate data for powerview devices."""
from __future__ import annotations

from datetime import timedelta
import logging

from aiopvapi.shades import Shades
import async_timeout

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import SHADE_DATA
from .shade_data import PowerviewShadeData

_LOGGER = logging.getLogger(__name__)


UPDATE_INTERVAL_DEFAULT = timedelta(seconds=60)
UPDATE_INTERVAL_MAINTENANCE = timedelta(minutes=5)


class PowerviewShadeUpdateCoordinator(DataUpdateCoordinator[PowerviewShadeData]):
    """DataUpdateCoordinator to gather data from a powerview hub."""

    def __init__(
        self,
        hass: HomeAssistant,
        shades: Shades,
        hub_address: str,
    ) -> None:
        """Initialize DataUpdateCoordinator to gather data for specific SmartPlug."""
        self.shades = shades
        self.maintenance = False
        super().__init__(
            hass,
            _LOGGER,
            name=f"powerview hub {hub_address}",
            update_interval=UPDATE_INTERVAL_DEFAULT,
        )

    async def _async_update_data(self) -> PowerviewShadeData:
        """Fetch data from shade endpoint."""

        if self.maintenance is True:
            self.update_interval = UPDATE_INTERVAL_DEFAULT
            self.maintenance = False
            _LOGGER.debug("Polling returned to %s", UPDATE_INTERVAL_DEFAULT)

        async with async_timeout.timeout(10):
            shade_entries = await self.shades.get_resources()

        if isinstance(shade_entries, bool):
            # hub returns boolean on a 204/423 empty response (maintenance)
            # continual polling results in inevitable error
            # restart of hub takes between 3-5 minutes and generally between 12am-3am
            _LOGGER.debug(
                "Hub maintenance underway. Pausing polling for %s",
                UPDATE_INTERVAL_MAINTENANCE,
            )
            self.update_interval = UPDATE_INTERVAL_MAINTENANCE
            self.maintenance = True
        elif not shade_entries:
            raise UpdateFailed("Failed to fetch new shade data")
        else:
            # only update if shade_entries is valid
            self.data.store_group_data(shade_entries[SHADE_DATA])

        return self.data
