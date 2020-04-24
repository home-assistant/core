"""The openweathermap component."""
import asyncio
import logging

from pyowm import OWM

from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_MODE,
    CONF_MONITORED_CONDITIONS,
    CONF_NAME,
)
from homeassistant.exceptions import ConfigEntryNotReady

from .const import (
    COMPONENTS,
    CONF_LANGUAGE,
    DOMAIN,
    ENTITY_NAME,
    FORECAST_COORDINATOR,
    MONITORED_CONDITIONS,
    WEATHER_COORDINATOR,
)
from .forecast_update_coordinator import ForecastUpdateCoordinator
from .weather_update_coordinator import WeatherUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config) -> bool:
    """Set up the OpenWeatherMap component."""
    return True


async def async_setup_entry(hass, config_entry):
    """Set up OpenWeatherMap as config entry."""
    name = config_entry.data[CONF_NAME]
    api_key = config_entry.data[CONF_API_KEY]
    latitude = config_entry.data[CONF_LATITUDE]
    longitude = config_entry.data[CONF_LONGITUDE]
    forecast_mode = config_entry.data[CONF_MODE]
    language = config_entry.data[CONF_LANGUAGE]
    monitored_conditions = config_entry.data[CONF_MONITORED_CONDITIONS]

    owm = OWM(API_key=api_key, language=language)
    weather_coordinator = WeatherUpdateCoordinator(owm, latitude, longitude, hass)
    forecast_coordinator = ForecastUpdateCoordinator(
        owm, latitude, longitude, forecast_mode, hass
    )

    await weather_coordinator.async_refresh()
    await forecast_coordinator.async_refresh()

    if (
        not weather_coordinator.last_update_success
        and not forecast_coordinator.last_update_success
    ):
        raise ConfigEntryNotReady

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][config_entry.entry_id] = {
        ENTITY_NAME: name,
        WEATHER_COORDINATOR: weather_coordinator,
        FORECAST_COORDINATOR: forecast_coordinator,
        MONITORED_CONDITIONS: monitored_conditions,
    }

    for component in COMPONENTS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, component)
        )

    return True


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(config_entry, component)
                for component in COMPONENTS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok
