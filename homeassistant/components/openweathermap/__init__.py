"""The openweathermap component."""
import asyncio
import logging

from pyowm import OWM

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_MODE,
    CONF_MONITORED_CONDITIONS,
    CONF_NAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import (
    COMPONENTS,
    CONF_LANGUAGE,
    DOMAIN,
    ENTRY_FORECAST_COORDINATOR,
    ENTRY_MONITORED_CONDITIONS,
    ENTRY_NAME,
    ENTRY_WEATHER_COORDINATOR,
)
from .forecast_update_coordinator import ForecastUpdateCoordinator
from .weather_update_coordinator import WeatherUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the OpenWeatherMap component."""
    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    """Set up OpenWeatherMap as config entry."""
    name = config_entry.data[CONF_NAME]
    api_key = config_entry.data[CONF_API_KEY]
    latitude = config_entry.data[CONF_LATITUDE]
    longitude = config_entry.data[CONF_LONGITUDE]
    forecast_mode = _get_config_value(config_entry, CONF_MODE)
    language = _get_config_value(config_entry, CONF_LANGUAGE)
    monitored_conditions_str = _get_config_value(
        config_entry, CONF_MONITORED_CONDITIONS
    )
    monitored_conditions = _get_monitored_conditions_list(monitored_conditions_str)

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
        ENTRY_NAME: name,
        ENTRY_WEATHER_COORDINATOR: weather_coordinator,
        ENTRY_FORECAST_COORDINATOR: forecast_coordinator,
        ENTRY_MONITORED_CONDITIONS: monitored_conditions,
    }

    for component in COMPONENTS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, component)
        )

    if not config_entry.update_listeners:
        config_entry.add_update_listener(async_update_options)

    return True


async def async_update_options(hass: HomeAssistant, config_entry: ConfigEntry):
    """Update options."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry):
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


def _get_config_value(config_entry, key):
    if config_entry.options:
        return config_entry.options[key]
    return config_entry.data[key]


def _get_monitored_conditions_list(string):
    return list(filter(None, str(string).split(",")))
