"""The WattTime integration."""
from __future__ import annotations

from datetime import timedelta

from aiowatttime import Client
from aiowatttime.emissions import RealTimeEmissionsResponseType
from aiowatttime.errors import WattTimeError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DATA_COORDINATOR, DOMAIN, LOGGER

DEFAULT_UPDATE_INTERVAL = timedelta(minutes=5)

PLATFORMS: list[str] = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up WattTime from a config entry."""
    hass.data.setdefault(DOMAIN, {DATA_COORDINATOR: {}})

    session = aiohttp_client.async_get_clientsession(hass)

    try:
        client = await Client.async_login(
            entry.data[CONF_USERNAME],
            entry.data[CONF_PASSWORD],
            session=session,
            logger=LOGGER,
        )
    except WattTimeError as err:
        LOGGER.error("Error while authenticating with WattTime: %s", err)
        return False

    async def async_update_data() -> RealTimeEmissionsResponseType:
        """Get the latest realtime emissions data."""
        try:
            return await client.emissions.async_get_realtime_emissions(
                entry.data[CONF_LATITUDE], entry.data[CONF_LONGITUDE]
            )
        except WattTimeError as err:
            raise UpdateFailed(
                f"Error while requesting data from WattTime: {err}"
            ) from err

    coordinator = DataUpdateCoordinator(
        hass,
        LOGGER,
        name=entry.title,
        update_interval=DEFAULT_UPDATE_INTERVAL,
        update_method=async_update_data,
    )

    await coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN][DATA_COORDINATOR][entry.entry_id] = coordinator

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN][DATA_COORDINATOR].pop(entry.entry_id)

    return unload_ok
