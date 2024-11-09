"""DataUpdateCoordinator for TechnoVE."""

from __future__ import annotations

from typing import TYPE_CHECKING

from technove import Station as TechnoVEStation, TechnoVE, TechnoVEError

from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER, SCAN_INTERVAL

if TYPE_CHECKING:
    from . import TechnoVEConfigEntry


class TechnoVEDataUpdateCoordinator(DataUpdateCoordinator[TechnoVEStation]):
    """Class to manage fetching TechnoVE data from single endpoint."""

    def __init__(self, hass: HomeAssistant, entry: TechnoVEConfigEntry) -> None:
        """Initialize global TechnoVE data updater."""
        self.technove = TechnoVE(
            entry.data[CONF_HOST],
            session=async_get_clientsession(hass),
        )
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> TechnoVEStation:
        """Fetch data from TechnoVE."""
        try:
            station = await self.technove.update()
        except TechnoVEError as error:
            raise UpdateFailed(f"Invalid response from API: {error}") from error

        return station
