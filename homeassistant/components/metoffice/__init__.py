"""The Met Office integration."""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

import datapoint

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import TimestampDataUpdateCoordinator

from .const import (
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    METOFFICE_COORDINATES,
    METOFFICE_DAILY_COORDINATOR,
    METOFFICE_HOURLY_COORDINATOR,
    METOFFICE_NAME,
    MODE_3HOURLY,
    MODE_DAILY,
)
from .data import MetOfficeData
from .helpers import fetch_data, fetch_site

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR, Platform.WEATHER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a Met Office entry."""

    latitude = entry.data[CONF_LATITUDE]
    longitude = entry.data[CONF_LONGITUDE]
    api_key = entry.data[CONF_API_KEY]
    site_name = entry.data[CONF_NAME]

    coordinates = f"{latitude}_{longitude}"

    @callback
    def update_unique_id(
        entity_entry: er.RegistryEntry,
    ) -> dict[str, Any] | None:
        """Update unique ID of entity entry."""

        if entity_entry.domain != Platform.SENSOR:
            return None

        name_to_key = {
            "Station Name": "name",
            "Weather": "weather",
            "Temperature": "temperature",
            "Feels Like Temperature": "feels_like_temperature",
            "Wind Speed": "wind_speed",
            "Wind Direction": "wind_direction",
            "Wind Gust": "wind_gust",
            "Visibility": "visibility",
            "Visibility Distance": "visibility_distance",
            "UV Index": "uv",
            "Probability of Precipitation": "precipitation",
            "Humidity": "humidity",
        }

        match = re.search(f"(?P<name>.*)_{coordinates}.*", entity_entry.unique_id)

        if match is None:
            return None

        if (name := match.group("name")) in name_to_key:
            return {
                "new_unique_id": entity_entry.unique_id.replace(name, name_to_key[name])
            }
        return None

    await er.async_migrate_entries(hass, entry.entry_id, update_unique_id)

    connection = datapoint.connection(api_key=api_key)

    site = await hass.async_add_executor_job(
        fetch_site, connection, latitude, longitude
    )
    if site is None:
        raise ConfigEntryNotReady

    async def async_update_3hourly() -> MetOfficeData:
        return await hass.async_add_executor_job(
            fetch_data, connection, site, MODE_3HOURLY
        )

    async def async_update_daily() -> MetOfficeData:
        return await hass.async_add_executor_job(
            fetch_data, connection, site, MODE_DAILY
        )

    metoffice_hourly_coordinator = TimestampDataUpdateCoordinator(
        hass,
        _LOGGER,
        config_entry=entry,
        name=f"MetOffice Hourly Coordinator for {site_name}",
        update_method=async_update_3hourly,
        update_interval=DEFAULT_SCAN_INTERVAL,
    )

    metoffice_daily_coordinator = TimestampDataUpdateCoordinator(
        hass,
        _LOGGER,
        config_entry=entry,
        name=f"MetOffice Daily Coordinator for {site_name}",
        update_method=async_update_daily,
        update_interval=DEFAULT_SCAN_INTERVAL,
    )

    metoffice_hass_data = hass.data.setdefault(DOMAIN, {})
    metoffice_hass_data[entry.entry_id] = {
        METOFFICE_HOURLY_COORDINATOR: metoffice_hourly_coordinator,
        METOFFICE_DAILY_COORDINATOR: metoffice_daily_coordinator,
        METOFFICE_NAME: site_name,
        METOFFICE_COORDINATES: coordinates,
    }

    # Fetch initial data so we have data when entities subscribe
    await asyncio.gather(
        metoffice_hourly_coordinator.async_config_entry_first_refresh(),
        metoffice_daily_coordinator.async_config_entry_first_refresh(),
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)
    return unload_ok


def get_device_info(coordinates: str, name: str) -> DeviceInfo:
    """Return device registry information."""
    return DeviceInfo(
        entry_type=dr.DeviceEntryType.SERVICE,
        identifiers={(DOMAIN, coordinates)},
        manufacturer="Met Office",
        name=f"Met Office {name}",
    )
