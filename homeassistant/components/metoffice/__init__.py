"""The Met Office integration."""

import asyncio
import logging

import datapoint

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import utcnow

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

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "weather"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a Met Office entry."""

    latitude = entry.data[CONF_LATITUDE]
    longitude = entry.data[CONF_LONGITUDE]
    api_key = entry.data[CONF_API_KEY]
    site_name = entry.data[CONF_NAME]

    connection = datapoint.connection(api_key=api_key)

    site = await hass.async_add_executor_job(
        _fetch_site, connection, latitude, longitude
    )
    if site is None:
        raise ConfigEntryNotReady()

    async def async_update_3hourly():
        return await hass.async_add_executor_job(
            _fetch_data, connection, site, MODE_3HOURLY
        )

    async def async_update_daily():
        return await hass.async_add_executor_job(
            _fetch_data, connection, site, MODE_DAILY
        )

    metoffice_hourly_coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"MetOffice Hourly Coordinator for {site_name}",
        update_method=async_update_3hourly,
        update_interval=DEFAULT_SCAN_INTERVAL,
    )

    metoffice_daily_coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"MetOffice Daily Coordinator for {site_name}",
        update_method=async_update_daily,
        update_interval=DEFAULT_SCAN_INTERVAL,
    )

    metoffice_hass_data = hass.data.setdefault(DOMAIN, {})
    metoffice_hass_data[entry.entry_id] = {
        METOFFICE_HOURLY_COORDINATOR: metoffice_hourly_coordinator,
        METOFFICE_DAILY_COORDINATOR: metoffice_daily_coordinator,
        METOFFICE_NAME: site_name,
        METOFFICE_COORDINATES: f"{latitude}_{longitude}",
    }

    # Fetch initial data so we have data when entities subscribe
    await asyncio.gather(
        metoffice_hourly_coordinator.async_config_entry_first_refresh(),
        metoffice_daily_coordinator.async_config_entry_first_refresh(),
    )

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)
    return unload_ok


def _fetch_site(connection, latitude, longitude):
    try:
        return connection.get_nearest_forecast_site(
            latitude=latitude, longitude=longitude
        )
    except datapoint.exceptions.APIException as err:
        _LOGGER.error("Received error from Met Office Datapoint: %s", err)
        return None


def _fetch_data(connection, site, mode):
    try:
        forecast = connection.get_forecast_for_site(site.id, mode)
    except (ValueError, datapoint.exceptions.APIException) as err:
        _LOGGER.error("Check Met Office connection: %s", err.args)
        raise UpdateFailed(err)
    else:
        time_now = utcnow()
        return MetOfficeData(
            forecast.now(),
            [
                timestep
                for day in forecast.days
                for timestep in day.timesteps
                if timestep.date > time_now
            ],
            site,
        )
