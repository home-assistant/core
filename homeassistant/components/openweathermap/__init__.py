"""The openweathermap component."""
import asyncio
import logging

from pyowm import OWM

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_MODE,
    CONF_NAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import (
    COMPONENTS,
    CONF_LANGUAGE,
    DOMAIN,
    ENTRY_FORECAST_COORDINATOR,
    ENTRY_NAME,
    ENTRY_WEATHER_COORDINATOR,
    UPDATE_LISTENER,
)
from .forecast_update_coordinator import ForecastUpdateCoordinator
from .weather_update_coordinator import WeatherUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the OpenWeatherMap component."""
    hass.data.setdefault(DOMAIN, {})

    weather_configs = _filter_domain_configs(config.get("weather", []), DOMAIN)
    sensor_configs = _filter_domain_configs(config.get("sensor", []), DOMAIN)

    _import_configs(hass, weather_configs + sensor_configs)
    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    """Set up OpenWeatherMap as config entry."""
    name = config_entry.data[CONF_NAME]
    api_key = config_entry.data[CONF_API_KEY]
    latitude = config_entry.data.get(CONF_LATITUDE, hass.config.latitude)
    longitude = config_entry.data.get(CONF_LONGITUDE, hass.config.longitude)
    forecast_mode = _get_config_value(config_entry, CONF_MODE)
    language = _get_config_value(config_entry, CONF_LANGUAGE)

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
    }

    for component in COMPONENTS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, component)
        )

    update_listener = config_entry.add_update_listener(async_update_options)
    hass.data[DOMAIN][config_entry.entry_id][UPDATE_LISTENER] = update_listener

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
        update_listener = hass.data[DOMAIN][config_entry.entry_id][UPDATE_LISTENER]
        update_listener()
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok


def _import_configs(hass, configs):
    for config in configs:
        _LOGGER.debug("Importing OpenWeatherMap %s", config)
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data=config,
            )
        )


def _filter_domain_configs(elements, domain):
    return list(filter(lambda elem: elem["platform"] == domain, elements))


def _get_config_value(config_entry, key):
    if config_entry.options:
        return config_entry.options[key]
    return config_entry.data[key]
