"""The openweathermap component."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from pyopenweathermap import OWMClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LANGUAGE,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_MODE,
    CONF_NAME,
)
from homeassistant.core import HomeAssistant

from .const import CONFIG_FLOW_VERSION, OWM_MODE_V25, PLATFORMS
from .coordinator import WeatherUpdateCoordinator
from .repairs import async_create_issue, async_delete_issue

_LOGGER = logging.getLogger(__name__)

type OpenweathermapConfigEntry = ConfigEntry[OpenweathermapData]


@dataclass
class OpenweathermapData:
    """Runtime data definition."""

    name: str
    coordinator: WeatherUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: OpenweathermapConfigEntry
) -> bool:
    """Set up OpenWeatherMap as config entry."""
    name = entry.data[CONF_NAME]
    api_key = entry.data[CONF_API_KEY]
    latitude = entry.data.get(CONF_LATITUDE, hass.config.latitude)
    longitude = entry.data.get(CONF_LONGITUDE, hass.config.longitude)
    language = _get_config_value(entry, CONF_LANGUAGE)
    mode = _get_config_value(entry, CONF_MODE)

    if mode == OWM_MODE_V25:
        async_create_issue(hass, entry.entry_id)
    else:
        async_delete_issue(hass, entry.entry_id)

    owm_client = OWMClient(api_key, mode, lang=language)
    weather_coordinator = WeatherUpdateCoordinator(
        owm_client, latitude, longitude, hass
    )

    await weather_coordinator.async_config_entry_first_refresh()

    entry.async_on_unload(entry.add_update_listener(async_update_options))

    entry.runtime_data = OpenweathermapData(name, weather_coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    config_entries = hass.config_entries
    data = entry.data
    version = entry.version

    _LOGGER.debug("Migrating OpenWeatherMap entry from version %s", version)

    if version < 3:
        new_data = {**data, CONF_MODE: OWM_MODE_V25}
        config_entries.async_update_entry(
            entry, data=new_data, version=CONFIG_FLOW_VERSION
        )

    _LOGGER.info("Migration to version %s successful", CONFIG_FLOW_VERSION)

    return True


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(
    hass: HomeAssistant, entry: OpenweathermapConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


def _get_config_value(config_entry: ConfigEntry, key: str) -> Any:
    if config_entry.options:
        return config_entry.options[key]
    return config_entry.data[key]
