"""Data coordinator for WeatherFlow Cloud Data."""
from datetime import timedelta
from random import randrange

from weatherflow4py.api import WeatherFlowRestAPI
from weatherflow4py.models.unified import WeatherFlowData

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import _LOGGER, DOMAIN


class WeatherFlowCloudDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching REST Based WeatherFlow Forecast data."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize global WeatherFlow forecast data updater."""

        # Store local variables
        self.hass = hass
        self.config_entry = config_entry

        # Extract API Token
        api_token = config_entry.data[CONF_API_TOKEN]
        self.weather_api = WeatherFlowRestAPI(api_token=api_token)

        self.data: dict[int, WeatherFlowData] = {}

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=randrange(25, 35)),
        )

    async def _async_update_data(self) -> dict[int, WeatherFlowData]:
        """Fetch data from WeatherFlow Forecast."""
        try:
            async with self.weather_api:
                self.data = await self.weather_api.get_all_data()
                return self.data
        except Exception as err:
            raise UpdateFailed(f"Update failed: {err}") from err
