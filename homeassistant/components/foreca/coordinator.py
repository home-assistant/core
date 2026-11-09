"""Data update coordinators for the Foreca integration."""

from dataclasses import dataclass
import logging
from typing import override

from pyforeca import (
    CurrentWeather,
    DailyForecast,
    ForecaApiClient,
    ForecaAuthError,
    ForecaError,
    ForecaProductUnavailableError,
    HourlyForecast,
    Observation,
    format_location,
)

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DAILY_PERIODS, DOMAIN, HOURLY_PERIODS, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


type ForecaConfigEntry = ConfigEntry[dict[str, ForecaLocationCoordinators]]


@dataclass(slots=True)
class ForecaWeatherData:
    """Weather data returned by the Foreca API."""

    current: CurrentWeather
    hourly: list[HourlyForecast]
    daily: list[DailyForecast]


class ForecaCoordinator[DataT](DataUpdateCoordinator[DataT]):
    """Base class for the coordinators of one Foreca location."""

    config_entry: ForecaConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ForecaConfigEntry,
        subentry: ConfigSubentry,
        client: ForecaApiClient,
        name: str,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=name,
            update_interval=UPDATE_INTERVAL,
            config_entry=entry,
        )
        self.client = client
        self.location = format_location(
            lon=subentry.data[CONF_LONGITUDE], lat=subentry.data[CONF_LATITUDE]
        )
        self.device_info = DeviceInfo(
            identifiers={(DOMAIN, subentry.subentry_id)},
            name=subentry.title,
            manufacturer="Foreca",
            entry_type=DeviceEntryType.SERVICE,
        )


class ForecaUpdateCoordinator(ForecaCoordinator[ForecaWeatherData]):
    """Class to manage fetching the Foreca forecast for one location."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ForecaConfigEntry,
        subentry: ConfigSubentry,
        client: ForecaApiClient,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(hass, entry, subentry, client, f"{DOMAIN} {subentry.title}")

    @override
    async def _async_update_data(self) -> ForecaWeatherData:
        """Fetch data from the Foreca API."""
        try:
            current = await self.client.current(self.location)
            hourly = await self.client.forecast_hourly(
                self.location, periods=HOURLY_PERIODS, dataset="full"
            )
            daily = await self.client.forecast_daily(
                self.location, periods=DAILY_PERIODS, dataset="full", ensemble=True
            )
        except (ForecaAuthError, ForecaProductUnavailableError) as err:
            raise ConfigEntryAuthFailed(
                f"The Foreca API rejected the API key: {err}"
            ) from err
        except ForecaError as err:
            raise UpdateFailed(
                f"Error communicating with the Foreca API: {err}"
            ) from err

        return ForecaWeatherData(current=current, hourly=hourly, daily=daily)


class ForecaObservationCoordinator(ForecaCoordinator[Observation | None]):
    """Class to manage fetching the nearest station's observation for one location."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ForecaConfigEntry,
        subentry: ConfigSubentry,
        client: ForecaApiClient,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass, entry, subentry, client, f"{DOMAIN} {subentry.title} observation"
        )

    @override
    async def _async_update_data(self) -> Observation | None:
        """Fetch the latest observation, or None where no station reports nearby."""
        try:
            return await self.client.observation_latest(self.location)
        except ForecaError as err:
            raise UpdateFailed(
                f"Error communicating with the Foreca API: {err}"
            ) from err


@dataclass(slots=True)
class ForecaLocationCoordinators:
    """The coordinators of one Foreca location."""

    weather: ForecaUpdateCoordinator
    observation: ForecaObservationCoordinator
