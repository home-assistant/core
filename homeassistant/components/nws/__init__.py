"""The National Weather Service integration."""
import asyncio
import datetime
import logging

from pynws import SimpleNWS

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import debounce
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_STATION,
    COORDINATOR_FORECAST,
    COORDINATOR_FORECAST_HOURLY,
    COORDINATOR_OBSERVATION,
    DOMAIN,
    NWS_DATA,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["weather"]

DEFAULT_SCAN_INTERVAL = datetime.timedelta(minutes=10)

DEBOUNCE_TIME = 60  # in seconds


def base_unique_id(latitude, longitude):
    """Return unique id for entries in configuration."""
    return f"{latitude}_{longitude}"


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the National Weather Service (NWS) component."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up a National Weather Service entry."""
    latitude = entry.data[CONF_LATITUDE]
    longitude = entry.data[CONF_LONGITUDE]
    api_key = entry.data[CONF_API_KEY]
    station = entry.data[CONF_STATION]

    client_session = async_get_clientsession(hass)

    # set_station only does IO when station is None
    nws_data = SimpleNWS(latitude, longitude, api_key, client_session)
    await nws_data.set_station(station)

    coordinator_observation = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"NWS observation station {station}",
        update_method=nws_data.update_observation,
        update_interval=DEFAULT_SCAN_INTERVAL,
        request_refresh_debouncer=debounce.Debouncer(
            hass, _LOGGER, cooldown=DEBOUNCE_TIME, immediate=True
        ),
    )

    coordinator_forecast = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"NWS forecast station {station}",
        update_method=nws_data.update_forecast,
        update_interval=DEFAULT_SCAN_INTERVAL,
        request_refresh_debouncer=debounce.Debouncer(
            hass, _LOGGER, cooldown=DEBOUNCE_TIME, immediate=True
        ),
    )

    coordinator_forecast_hourly = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"NWS forecast hourly station {station}",
        update_method=nws_data.update_forecast_hourly,
        update_interval=DEFAULT_SCAN_INTERVAL,
        request_refresh_debouncer=debounce.Debouncer(
            hass, _LOGGER, cooldown=DEBOUNCE_TIME, immediate=True
        ),
    )
    nws_hass_data = hass.data.setdefault(DOMAIN, {})
    nws_hass_data[entry.entry_id] = {
        NWS_DATA: nws_data,
        COORDINATOR_OBSERVATION: coordinator_observation,
        COORDINATOR_FORECAST: coordinator_forecast,
        COORDINATOR_FORECAST_HOURLY: coordinator_forecast_hourly,
    }

    # Fetch initial data so we have data when entities subscribe
    await coordinator_observation.async_refresh()
    await coordinator_forecast.async_refresh()
    await coordinator_forecast_hourly.async_refresh()

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        if len(hass.data[DOMAIN]) == 0:
            hass.data.pop(DOMAIN)
    return unload_ok
