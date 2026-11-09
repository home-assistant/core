"""The AEMET OpenData component."""

import shutil

from aemet_opendata.exceptions import AemetError, AuthError, TownNotFound
from aemet_opendata.interface import AEMET, ConnectionOptions, UpdateFeature

from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.storage import STORAGE_DIR

from .const import CONF_RADAR_UPDATES, CONF_STATION_UPDATES, DOMAIN, PLATFORMS
from .coordinator import AemetConfigEntry, AemetData, WeatherUpdateCoordinator
from .reminder import async_dismiss_api_key_reminder, async_schedule_api_key_reminder


async def async_setup_entry(hass: HomeAssistant, entry: AemetConfigEntry) -> None:
    """Set up AEMET OpenData as config entry."""
    name = entry.data.get(CONF_NAME) or entry.title
    api_key = entry.data[CONF_API_KEY]
    latitude = entry.data[CONF_LATITUDE]
    longitude = entry.data[CONF_LONGITUDE]
    update_features: int = UpdateFeature.FORECAST
    if entry.options.get(CONF_RADAR_UPDATES, False):
        update_features |= UpdateFeature.RADAR
    if entry.options.get(CONF_STATION_UPDATES, True):
        update_features |= UpdateFeature.STATION

    options = ConnectionOptions(api_key, update_features)
    aemet = AEMET(aiohttp_client.async_get_clientsession(hass), options)
    aemet.set_api_data_dir(hass.config.path(STORAGE_DIR, f"{DOMAIN}-{entry.unique_id}"))

    try:
        await aemet.select_coordinates(latitude, longitude)
    except TownNotFound as err:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="town_not_found",
            translation_placeholders={
                "latitude": str(latitude),
                "longitude": str(longitude),
            },
        ) from err
    except AuthError as err:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="invalid_api_key",
        ) from err
    except AemetError as err:
        raise ConfigEntryNotReady(err) from err

    weather_coordinator = WeatherUpdateCoordinator(hass, entry, aemet)
    await weather_coordinator.async_config_entry_first_refresh()

    entry.runtime_data = AemetData(name=name, coordinator=weather_coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_update_options))

    if reminder_unsub := async_schedule_api_key_reminder(hass, entry):
        weather_coordinator.reminder_unsub = reminder_unsub
        entry.async_on_unload(reminder_unsub)


async def async_update_options(hass: HomeAssistant, entry: AemetConfigEntry) -> None:
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: AemetConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
    async_dismiss_api_key_reminder(hass, entry)


async def async_remove_entry(hass: HomeAssistant, entry: AemetConfigEntry) -> None:
    """Remove a config entry."""
    async_dismiss_api_key_reminder(hass, entry)
    await hass.async_add_executor_job(
        shutil.rmtree,
        hass.config.path(STORAGE_DIR, f"{DOMAIN}-{entry.unique_id}"),
    )
