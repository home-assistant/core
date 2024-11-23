"""The Met Office integration."""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

import datapoint
import datapoint.Forecast
import datapoint.Manager

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
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
)
from .helpers import fetch_data

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

        key_mapping = {
            "weather": "significantWeatherCode",
            "temperature": "screenTemperature",
            "feels_like_temperature": "feelsLikeTemperature",
            "wind_speed": "windSpeed10m",
            "wind_direction": "windDirectionFrom10m",
            "wind_gust": "windGustSpeed10m",
            "uv": "uvIndex",
            "precipitation": "probOfPrecipitation",
            "humidity": "screenRelativeHumidity",
        }

        match = re.search(f"(?P<key>.*)_{coordinates}.*", entity_entry.unique_id)

        if match is None:
            return None

        if (old_key := match.group("key")) in key_mapping:
            return {
                "new_unique_id": entity_entry.unique_id.replace(
                    old_key, key_mapping[old_key]
                )
            }
        return None

    await er.async_migrate_entries(hass, entry.entry_id, update_unique_id)

    connection = datapoint.Manager.Manager(api_key=api_key)

    async def async_update_daily() -> datapoint.Forecast:
        return await hass.async_add_executor_job(
            fetch_data, connection, latitude, longitude, "daily"
        )

    async def async_update_hourly() -> datapoint.Forecast:
        return await hass.async_add_executor_job(
            fetch_data, connection, latitude, longitude, "hourly"
        )

    metoffice_daily_coordinator = TimestampDataUpdateCoordinator(
        hass,
        _LOGGER,
        config_entry=entry,
        name=f"MetOffice Daily Coordinator for {site_name}",
        update_method=async_update_daily,
        update_interval=DEFAULT_SCAN_INTERVAL,
    )

    metoffice_hourly_coordinator = TimestampDataUpdateCoordinator(
        hass,
        _LOGGER,
        config_entry=entry,
        name=f"MetOffice Hourly Coordinator for {site_name}",
        update_method=async_update_hourly,
        update_interval=DEFAULT_SCAN_INTERVAL,
    )

    metoffice_hass_data = hass.data.setdefault(DOMAIN, {})
    metoffice_hass_data[entry.entry_id] = {
        METOFFICE_DAILY_COORDINATOR: metoffice_daily_coordinator,
        METOFFICE_HOURLY_COORDINATOR: metoffice_hourly_coordinator,
        METOFFICE_NAME: site_name,
        METOFFICE_COORDINATES: coordinates,
    }

    # Fetch initial data so we have data when entities subscribe
    await asyncio.gather(
        metoffice_daily_coordinator.async_config_entry_first_refresh(),
        metoffice_hourly_coordinator.async_config_entry_first_refresh(),
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
