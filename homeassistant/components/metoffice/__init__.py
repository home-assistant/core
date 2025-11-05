"""The Met Office integration."""

from __future__ import annotations

import asyncio
import logging

from datapoint.Forecast import Forecast
from datapoint.Manager import Manager

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import TimestampDataUpdateCoordinator

from .const import (
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    METOFFICE_COORDINATES,
    METOFFICE_DAILY_COORDINATOR,
    METOFFICE_HOURLY_COORDINATOR,
    METOFFICE_NAME,
    METOFFICE_TWICE_DAILY_COORDINATOR,
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

    connection = Manager(api_key=api_key)

    async def async_update_hourly() -> Forecast:
        return await hass.async_add_executor_job(
            fetch_data, connection, latitude, longitude, "hourly"
        )

    async def async_update_daily() -> Forecast:
        return await hass.async_add_executor_job(
            fetch_data, connection, latitude, longitude, "daily"
        )

    async def async_update_twice_daily() -> Forecast:
        return await hass.async_add_executor_job(
            fetch_data, connection, latitude, longitude, "twice-daily"
        )

    metoffice_hourly_coordinator = TimestampDataUpdateCoordinator(
        hass,
        _LOGGER,
        config_entry=entry,
        name=f"MetOffice Hourly Coordinator for {site_name}",
        update_method=async_update_hourly,
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

    metoffice_twice_daily_coordinator = TimestampDataUpdateCoordinator(
        hass,
        _LOGGER,
        config_entry=entry,
        name=f"MetOffice Twice Daily Coordinator for {site_name}",
        update_method=async_update_twice_daily,
        update_interval=DEFAULT_SCAN_INTERVAL,
    )

    metoffice_hass_data = hass.data.setdefault(DOMAIN, {})
    metoffice_hass_data[entry.entry_id] = {
        METOFFICE_HOURLY_COORDINATOR: metoffice_hourly_coordinator,
        METOFFICE_DAILY_COORDINATOR: metoffice_daily_coordinator,
        METOFFICE_TWICE_DAILY_COORDINATOR: metoffice_twice_daily_coordinator,
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
