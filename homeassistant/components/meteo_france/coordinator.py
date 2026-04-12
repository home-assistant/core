"""Support for Meteo-France weather data."""

from datetime import timedelta
import logging

from meteofrance_api.client import MeteoFranceClient
from meteofrance_api.model import CurrentPhenomenons, Forecast, Rain

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL_RAIN = timedelta(minutes=5)
SCAN_INTERVAL = timedelta(minutes=15)


class MeteoFranceForecastUpdateCoordinator(DataUpdateCoordinator[Forecast]):
    """Coordinator for Meteo-France forecast data."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: MeteoFranceClient,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"Météo-France forecast for city {entry.title}",
            config_entry=entry,
            update_interval=SCAN_INTERVAL,
        )
        self._client = client
        self._latitude = entry.data[CONF_LATITUDE]
        self._longitude = entry.data[CONF_LONGITUDE]

    async def _async_update_data(self) -> Forecast:
        """Get data from Meteo-France forecast."""
        return await self.hass.async_add_executor_job(
            self._client.get_forecast, self._latitude, self._longitude
        )


class MeteoFranceRainUpdateCoordinator(DataUpdateCoordinator[Rain]):
    """Coordinator for Meteo-France rain data."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: MeteoFranceClient,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"Météo-France rain for city {entry.title}",
            config_entry=entry,
            update_interval=SCAN_INTERVAL_RAIN,
        )
        self._client = client
        self._latitude = entry.data[CONF_LATITUDE]
        self._longitude = entry.data[CONF_LONGITUDE]

    async def _async_update_data(self) -> Rain:
        """Get data from Meteo-France rain."""
        return await self.hass.async_add_executor_job(
            self._client.get_rain, self._latitude, self._longitude
        )


class MeteoFranceAlertUpdateCoordinator(DataUpdateCoordinator[CurrentPhenomenons]):
    """Coordinator for Meteo-France alert data."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: MeteoFranceClient,
        department: str,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"Météo-France alert for department {department}",
            config_entry=entry,
            update_interval=SCAN_INTERVAL,
        )
        self._client = client
        self._department = department

    async def _async_update_data(self) -> CurrentPhenomenons:
        """Get data from Meteo-France alert."""
        return await self.hass.async_add_executor_job(
            self._client.get_warning_current_phenomenons, self._department, 0, True
        )
