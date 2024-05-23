"""Define an object to manage fetching AirGradient data."""

from datetime import timedelta

from airgradient import AirGradientClient, AirGradientError, Measures

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import LOGGER


class AirGradientDataUpdateCoordinator(DataUpdateCoordinator[Measures]):
    """Class to manage fetching AirGradient data."""

    def __init__(self, hass: HomeAssistant, host: str) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            logger=LOGGER,
            name=f"AirGradient {host}",
            update_interval=timedelta(minutes=1),
        )
        session = async_get_clientsession(hass)
        self.client = AirGradientClient(host, session=session)

    async def _async_update_data(self) -> Measures:
        try:
            return await self.client.get_current_measures()
        except AirGradientError as error:
            raise UpdateFailed(error) from error
