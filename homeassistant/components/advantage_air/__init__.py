"""Advantage Air climate integration."""

import asyncio
from datetime import timedelta
import logging

from advantage_air import ApiError, advantage_air

from homeassistant.const import CONF_IP_ADDRESS, CONF_PORT
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import ADVANTAGE_AIR_RETRY, DOMAIN

ADVANTAGE_AIR_SYNC_INTERVAL = 15
PLATFORMS = ["climate", "cover", "binary_sensor", "sensor", "switch"]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry):
    """Set up Advantage Air config."""
    ip_address = entry.data[CONF_IP_ADDRESS]
    port = entry.data[CONF_PORT]
    api = advantage_air(
        ip_address,
        port=port,
        session=async_get_clientsession(hass),
        retry=ADVANTAGE_AIR_RETRY,
    )

    async def async_get():
        try:
            return await api.async_get()
        except ApiError as err:
            raise UpdateFailed(err) from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="Advantage Air",
        update_method=async_get,
        update_interval=timedelta(seconds=ADVANTAGE_AIR_SYNC_INTERVAL),
    )

    async def async_change(change):
        try:
            if await api.async_change(change):
                await coordinator.async_refresh()
        except ApiError as err:
            _LOGGER.warning(err)

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "async_change": async_change,
    }

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    return True


async def async_unload_entry(hass, entry):
    """Unload Advantage Air Config."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
            ]
        )
    )

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
