"""Define an object to coordinate fetching Overseerr data."""

from datetime import timedelta

from python_overseerr import OverseerrClient, RequestCount
from python_overseerr.exceptions import OverseerrConnectionError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_PORT, CONF_SSL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER

type OverseerrConfigEntry = ConfigEntry[OverseerrCoordinator]


class OverseerrCoordinator(DataUpdateCoordinator[RequestCount]):
    """Class to manage fetching Overseerr data."""

    config_entry: OverseerrConfigEntry

    def __init__(self, hass: HomeAssistant, entry: OverseerrConfigEntry) -> None:
        """Initialize."""
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=timedelta(minutes=5),
        )
        self.client = OverseerrClient(
            entry.data[CONF_HOST],
            entry.data[CONF_PORT],
            entry.data[CONF_API_KEY],
            ssl=entry.data[CONF_SSL],
            session=async_get_clientsession(hass),
        )

    async def _async_update_data(self) -> RequestCount:
        """Fetch data from API endpoint."""
        try:
            return await self.client.get_request_count()
        except OverseerrConnectionError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="connection_error",
                translation_placeholders={"error": str(err)},
            ) from err
