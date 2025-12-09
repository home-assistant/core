"""The Google Weather integration."""

from __future__ import annotations

import asyncio

from google_weather_api import GoogleWeatherApi

from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_REFERRER
from .coordinator import (
    GoogleWeatherConfigEntry,
    GoogleWeatherCurrentConditionsCoordinator,
    GoogleWeatherDailyForecastCoordinator,
    GoogleWeatherHourlyForecastCoordinator,
    GoogleWeatherRuntimeData,
    GoogleWeatherSubEntryRuntimeData,
)

_PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.WEATHER]


async def async_setup_entry(
    hass: HomeAssistant, entry: GoogleWeatherConfigEntry
) -> bool:
    """Set up Google Weather from a config entry."""

    api = GoogleWeatherApi(
        session=async_get_clientsession(hass),
        api_key=entry.data[CONF_API_KEY],
        referrer=entry.data.get(CONF_REFERRER),
        language_code=hass.config.language,
    )
    subentries_runtime_data: dict[str, GoogleWeatherSubEntryRuntimeData] = {}
    for subentry in entry.subentries.values():
        subentry_runtime_data = GoogleWeatherSubEntryRuntimeData(
            coordinator_observation=GoogleWeatherCurrentConditionsCoordinator(
                hass, entry, subentry, api
            ),
            coordinator_daily_forecast=GoogleWeatherDailyForecastCoordinator(
                hass, entry, subentry, api
            ),
            coordinator_hourly_forecast=GoogleWeatherHourlyForecastCoordinator(
                hass, entry, subentry, api
            ),
        )
        subentries_runtime_data[subentry.subentry_id] = subentry_runtime_data
    tasks = [
        coro
        for subentry_runtime_data in subentries_runtime_data.values()
        for coro in (
            subentry_runtime_data.coordinator_observation.async_config_entry_first_refresh(),
            subentry_runtime_data.coordinator_daily_forecast.async_config_entry_first_refresh(),
            subentry_runtime_data.coordinator_hourly_forecast.async_config_entry_first_refresh(),
        )
    ]
    await asyncio.gather(*tasks)
    entry.runtime_data = GoogleWeatherRuntimeData(
        api=api,
        subentries_runtime_data=subentries_runtime_data,
    )

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: GoogleWeatherConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)


async def async_update_options(
    hass: HomeAssistant, entry: GoogleWeatherConfigEntry
) -> None:
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)
