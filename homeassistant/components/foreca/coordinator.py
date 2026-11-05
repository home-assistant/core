"""Data update coordinator for the Foreca integration."""

from collections.abc import Awaitable
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

from .const import (
    DAILY_PERIODS,
    DOMAIN,
    HOURLY_PERIODS,
    UPDATE_INTERVAL,
    OptionalRequest,
)

_LOGGER = logging.getLogger(__name__)

type ForecaConfigEntry = ConfigEntry[dict[str, ForecaUpdateCoordinator]]


@dataclass(slots=True)
class ForecaWeatherData:
    """Weather data returned by the Foreca API."""

    current: CurrentWeather
    hourly: list[HourlyForecast]
    daily: list[DailyForecast]
    observation: Observation | None
    failed_requests: frozenset[OptionalRequest]


class ForecaUpdateCoordinator(DataUpdateCoordinator[ForecaWeatherData]):
    """Class to manage fetching Foreca data for one location."""

    config_entry: ForecaConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ForecaConfigEntry,
        subentry: ConfigSubentry,
        client: ForecaApiClient,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} {subentry.title}",
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
        self._failed_requests: set[OptionalRequest] = set()

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
            observation = await self._async_optional(
                OptionalRequest.OBSERVATION,
                self.client.observation_latest(self.location),
            )
        except (ForecaAuthError, ForecaProductUnavailableError) as err:
            raise ConfigEntryAuthFailed(
                f"The Foreca API rejected the API key: {err}"
            ) from err
        except ForecaError as err:
            raise UpdateFailed(
                f"Error communicating with the Foreca API: {err}"
            ) from err

        return ForecaWeatherData(
            current=current,
            hourly=hourly,
            daily=daily,
            observation=observation,
            failed_requests=frozenset(self._failed_requests),
        )

    async def _async_optional[T](
        self, request: OptionalRequest, response: Awaitable[T]
    ) -> T | None:
        """Return the response of a request the update can do without.

        If the request fails, return None and mark it failed, so that only the
        sensors reading it become unavailable. A rejected key still fails the
        whole update.
        """
        try:
            result = await response
        except ForecaAuthError:
            raise
        except ForecaError as err:
            if request not in self._failed_requests:
                self._failed_requests.add(request)
                _LOGGER.info("Error fetching %s %s data: %s", self.name, request, err)
            return None
        if request in self._failed_requests:
            self._failed_requests.remove(request)
            _LOGGER.info("Fetching %s %s data recovered", self.name, request)
        return result
