"""The Met Office integration."""

import asyncio

from datapoint.Manager import Manager

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
    CONF_NAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN
from .coordinator import (
    MetOfficeConfigEntry,
    MetOfficeRuntimeData,
    MetOfficeUpdateCoordinator,
)

PLATFORMS = [Platform.SENSOR, Platform.WEATHER]


async def async_setup_entry(hass: HomeAssistant, entry: MetOfficeConfigEntry) -> None:
    """Set up a Met Office entry."""

    latitude: float = entry.data[CONF_LOCATION][CONF_LATITUDE]
    longitude: float = entry.data[CONF_LOCATION][CONF_LONGITUDE]
    api_key: str = entry.data[CONF_API_KEY]
    site_name: str = entry.data[CONF_NAME]

    connection = Manager(api_key=api_key)

    metoffice_hourly_coordinator = MetOfficeUpdateCoordinator(
        hass,
        entry,
        name=f"MetOffice Hourly Coordinator for {site_name}",
        connection=connection,
        latitude=latitude,
        longitude=longitude,
        frequency="hourly",
    )

    metoffice_daily_coordinator = MetOfficeUpdateCoordinator(
        hass,
        entry,
        name=f"MetOffice Daily Coordinator for {site_name}",
        connection=connection,
        latitude=latitude,
        longitude=longitude,
        frequency="daily",
    )

    metoffice_twice_daily_coordinator = MetOfficeUpdateCoordinator(
        hass,
        entry,
        name=f"MetOffice Twice Daily Coordinator for {site_name}",
        connection=connection,
        latitude=latitude,
        longitude=longitude,
        frequency="twice-daily",
    )

    # Fetch initial data so we have data when entities subscribe
    await asyncio.gather(
        metoffice_hourly_coordinator.async_config_entry_first_refresh(),
        metoffice_daily_coordinator.async_config_entry_first_refresh(),
    )

    entry.runtime_data = MetOfficeRuntimeData(
        coordinates=f"{latitude}_{longitude}",
        hourly_coordinator=metoffice_hourly_coordinator,
        daily_coordinator=metoffice_daily_coordinator,
        twice_daily_coordinator=metoffice_twice_daily_coordinator,
        name=site_name,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)


def get_device_info(coordinates: str, name: str) -> DeviceInfo:
    """Return device registry information."""
    return DeviceInfo(
        entry_type=dr.DeviceEntryType.SERVICE,
        identifiers={(DOMAIN, coordinates)},
        manufacturer="Met Office",
        name=f"Met Office {name}",
    )


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Migrate old config entry."""

    if entry.version < 2:
        data = dict(entry.data)
        long = data.pop(CONF_LONGITUDE)
        lat = data.pop(CONF_LATITUDE)
        data[CONF_LOCATION] = {CONF_LATITUDE: lat, CONF_LONGITUDE: long}
        hass.config_entries.async_update_entry(entry, data=data, version=2)
