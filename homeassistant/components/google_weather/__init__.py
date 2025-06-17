"""The Google Weather integration."""

from __future__ import annotations

import asyncio

from google_weather_api import GoogleWeatherApi

from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_REFERRER
from .coordinator import (
    GoogleWeatherConfigEntry,
    GoogleWeatherCurrentConditionsCoordinator,
    GoogleWeatherDailyForecastCoordinator,
    GoogleWeatherHourlyForecastCoordinator,
    GoogleWeatherRuntimeData,
)

_PLATFORMS: list[Platform] = [Platform.WEATHER]


async def async_setup_entry(
    hass: HomeAssistant, entry: GoogleWeatherConfigEntry
) -> bool:
    """Set up Google Weather from a config entry."""

    api = GoogleWeatherApi(
        session=async_get_clientsession(hass),
        api_key=entry.data[CONF_API_KEY],
        referrer=entry.data.get(CONF_REFERRER),
        latitude=entry.data[CONF_LATITUDE],
        longitude=entry.data[CONF_LONGITUDE],
        language_code=hass.config.language,
    )
    coordinator_observation = GoogleWeatherCurrentConditionsCoordinator(
        hass, entry, api
    )
    coordinator_daily_forecast = GoogleWeatherDailyForecastCoordinator(hass, entry, api)
    coordinator_hourly_forecast = GoogleWeatherHourlyForecastCoordinator(
        hass, entry, api
    )
    await asyncio.gather(
        coordinator_observation.async_config_entry_first_refresh(),
        coordinator_daily_forecast.async_config_entry_first_refresh(),
        coordinator_hourly_forecast.async_config_entry_first_refresh(),
    )
    entry.runtime_data = GoogleWeatherRuntimeData(
        coordinator_observation=coordinator_observation,
        coordinator_daily_forecast=coordinator_daily_forecast,
        coordinator_hourly_forecast=coordinator_hourly_forecast,
    )

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: GoogleWeatherConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
