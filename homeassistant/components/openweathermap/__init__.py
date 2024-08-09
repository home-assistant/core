"""The openweathermap component."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from pyopenweathermap import OWMClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LANGUAGE,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_MODE,
    CONF_NAME,
    CONF_ZONE,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers.event import async_track_state_change_event

from .const import CONFIG_FLOW_VERSION, OWM_MODE_V25, PLATFORMS
from .coordinator import WeatherUpdateCoordinator
from .repairs import async_create_issue, async_delete_issue
from .utils import build_data_and_options

_LOGGER = logging.getLogger(__name__)

type OpenweathermapConfigEntry = ConfigEntry[OpenweathermapData]


@dataclass
class OpenweathermapData:
    """Runtime data definition."""

    name: str
    coordinator: WeatherUpdateCoordinator
    event_unsubscribe: CALLBACK_TYPE | None = None


async def async_setup_entry(
    hass: HomeAssistant, entry: OpenweathermapConfigEntry
) -> bool:
    """Set up OpenWeatherMap as config entry."""
    name = entry.data[CONF_NAME]
    api_key = entry.data[CONF_API_KEY]
    zone = entry.data.get(CONF_ZONE)
    if zone:
        zone_state = hass.states.get(zone)
        if zone_state:
            latitude = zone_state.attributes.get("latitude")
            longitude = zone_state.attributes.get("longitude")
    else:
        latitude = entry.data.get(CONF_LATITUDE, hass.config.latitude)
        longitude = entry.data.get(CONF_LONGITUDE, hass.config.longitude)
    language = entry.options[CONF_LANGUAGE]
    mode = entry.options[CONF_MODE]

    if mode == OWM_MODE_V25:
        async_create_issue(hass, entry.entry_id)
    else:
        async_delete_issue(hass, entry.entry_id)

    owm_client = OWMClient(api_key, mode, lang=language)
    weather_coordinator = WeatherUpdateCoordinator(
        owm_client, latitude, longitude, hass
    )

    event_unsubscribe = None
    if zone:
        event_unsubscribe = async_track_state_change_event(
            hass, zone, weather_coordinator.zone_update
        )

    await weather_coordinator.async_config_entry_first_refresh()

    entry.async_on_unload(entry.add_update_listener(async_update_options))

    entry.runtime_data = OpenweathermapData(
        name, weather_coordinator, event_unsubscribe
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    config_entries = hass.config_entries
    data = entry.data
    options = entry.options
    version = entry.version

    _LOGGER.debug("Migrating OpenWeatherMap entry from version %s", version)

    if version < 5:
        combined_data = {**data, **options, CONF_MODE: OWM_MODE_V25}
        new_data, new_options = build_data_and_options(combined_data)
        config_entries.async_update_entry(
            entry,
            data=new_data,
            options=new_options,
            version=CONFIG_FLOW_VERSION,
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
    if entry.runtime_data.event_unsubscribe is not None:
        entry.runtime_data.event_unsubscribe()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
