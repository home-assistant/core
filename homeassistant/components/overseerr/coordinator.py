"""Define an object to coordinate fetching Overseerr data."""

from datetime import timedelta

from python_overseerr import OverseerrClient, RequestCount
from python_overseerr.exceptions import OverseerrConnectionError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER

type OverseerrConfigEntry = ConfigEntry[OverseerrCoordinator]


class OverseerrCoordinator(DataUpdateCoordinator[RequestCount]):
    """Class to manage fetching Overseerr data."""

    config_entry: OverseerrConfigEntry

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize."""
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=5),
        )
        self.client = OverseerrClient(
            self.config_entry.data[CONF_HOST],
            self.config_entry.data[CONF_API_KEY],
            session=async_get_clientsession(hass),
        )

    async def _async_update_data(self) -> RequestCount:
        """Fetch data from API endpoint."""
        try:
            return await self.client.get_request_count()
        except OverseerrConnectionError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
