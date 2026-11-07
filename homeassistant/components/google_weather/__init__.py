"""The Google Weather integration."""

import asyncio

from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import CONF_REFERRER, DOMAIN
from .coordinator import (
    GoogleWeatherConfigEntry,
    GoogleWeatherCurrentConditionsCoordinator,
    GoogleWeatherDailyForecastCoordinator,
    GoogleWeatherHourlyForecastCoordinator,
    GoogleWeatherRuntimeData,
    GoogleWeatherSubEntryRuntimeData,
    create_api,
)
from .services import async_setup_services

_PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.WEATHER]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Google Weather integration."""
    async_setup_services(hass)
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: GoogleWeatherConfigEntry
) -> None:
    """Set up Google Weather from a config entry."""

    api = create_api(hass, entry.data[CONF_API_KEY], entry.data.get(CONF_REFERRER))
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
    # Wait for every refresh to settle before failing, so that no refresh outlives
    # a setup that did not complete. Exceptions are re-raised as-is, so that
    # ConfigEntryNotReady and ConfigEntryAuthFailed keep their meaning.
    results = await asyncio.gather(
        *(
            coordinator.async_config_entry_first_refresh()
            for subentry_runtime_data in subentries_runtime_data.values()
            for coordinator in (
                subentry_runtime_data.coordinator_observation,
                subentry_runtime_data.coordinator_daily_forecast,
                subentry_runtime_data.coordinator_hourly_forecast,
            )
        ),
        return_exceptions=True,
    )
    for result in results:
        if isinstance(result, BaseException):
            raise result
    entry.runtime_data = GoogleWeatherRuntimeData(
        api=api,
        subentries_runtime_data=subentries_runtime_data,
    )

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_update_options))


async def async_unload_entry(
    hass: HomeAssistant, entry: GoogleWeatherConfigEntry
) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, _PLATFORMS)


async def async_update_options(
    hass: HomeAssistant, entry: GoogleWeatherConfigEntry
) -> None:
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)
