"""The AccuWeather component."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from accuweather import AccuWeather, ApiError, InvalidApiKeyError, RequestsExceededError
from aiohttp import ClientSession
from aiohttp.client_exceptions import ClientConnectorError
from async_timeout import timeout

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import ATTR_FORECAST, CONF_FORECAST, DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR, Platform.WEATHER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up AccuWeather as config entry."""
    api_key: str = entry.data[CONF_API_KEY]
    assert entry.unique_id is not None
    location_key = entry.unique_id
    forecast: bool = entry.options.get(CONF_FORECAST, False)

    _LOGGER.debug("Using location_key: %s, get forecast: %s", location_key, forecast)

    websession = async_get_clientsession(hass)

    coordinator = AccuWeatherDataUpdateCoordinator(
        hass, websession, api_key, location_key, forecast
    )
    await coordinator.async_config_entry_first_refresh()

    entry.async_on_unload(entry.add_update_listener(update_listener))

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update listener."""
    await hass.config_entries.async_reload(entry.entry_id)


class AccuWeatherDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching AccuWeather data API."""

    def __init__(
        self,
        hass: HomeAssistant,
        session: ClientSession,
        api_key: str,
        location_key: str,
        forecast: bool,
    ) -> None:
        """Initialize."""
        self.location_key = location_key
        self.forecast = forecast
        self.is_metric = hass.config.units.is_metric
        self.accuweather = AccuWeather(api_key, session, location_key=self.location_key)

        # Enabling the forecast download increases the number of requests per data
        # update, we use 40 minutes for current condition only and 80 minutes for
        # current condition and forecast as update interval to not exceed allowed number
        # of requests. We have 50 requests allowed per day, so we use 36 and leave 14 as
        # a reserve for restarting HA.
        update_interval = timedelta(minutes=40)
        if self.forecast:
            update_interval *= 2
        _LOGGER.debug("Data will be update every %s", update_interval)

        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=update_interval)

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via library."""
        try:
            async with timeout(10):
                current = await self.accuweather.async_get_current_conditions()
                forecast = (
                    await self.accuweather.async_get_forecast(metric=self.is_metric)
                    if self.forecast
                    else {}
                )
        except (
            ApiError,
            ClientConnectorError,
            InvalidApiKeyError,
            RequestsExceededError,
        ) as error:
            raise UpdateFailed(error) from error
        _LOGGER.debug("Requests remaining: %d", self.accuweather.requests_remaining)
        return {**current, **{ATTR_FORECAST: forecast}}
