"""The Forecast.Solar integration."""
from __future__ import annotations

from datetime import timedelta
import logging

from forecast_solar import ForecastSolar

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_AZIMUTH,
    CONF_DAMPING,
    CONF_DECLINATION,
    CONF_MODULES_POWER,
    DOMAIN,
)

PLATFORMS = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Forecast.Solar from a config entry."""
    api_key = entry.options.get(CONF_API_KEY)
    # Our option flow may cause it to be an empty string,
    # this if statement is here to catch that.
    if not api_key:
        api_key = None

    session = async_get_clientsession(hass)
    forecast = ForecastSolar(
        api_key=api_key,
        session=session,
        latitude=entry.data[CONF_LATITUDE],
        longitude=entry.data[CONF_LONGITUDE],
        declination=entry.options[CONF_DECLINATION],
        azimuth=(entry.options[CONF_AZIMUTH] - 180),
        kwp=(entry.options[CONF_MODULES_POWER] / 1000),
        damping=entry.options.get(CONF_DAMPING, 0),
    )

    # Free account have a resolution of 1 hour, using that as the default
    # update interval. Using a higher value for accounts with an API key.
    update_interval = timedelta(hours=1)
    if api_key is not None:
        update_interval = timedelta(minutes=30)

    coordinator: DataUpdateCoordinator = DataUpdateCoordinator(
        hass,
        logging.getLogger(__name__),
        name=DOMAIN,
        update_method=forecast.estimate,
        update_interval=update_interval,
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)
