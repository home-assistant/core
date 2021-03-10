"""The Mullvad VPN integration."""
import asyncio
from datetime import timedelta
import logging

import async_timeout
from mullvad_api import MullvadAPI

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import update_coordinator

from .const import DOMAIN

PLATFORMS = ["binary_sensor"]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Mullvad VPN integration."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: dict):
    """Set up Mullvad VPN integration."""

    async def async_get_mullvad_api_data():
        with async_timeout.timeout(10):
            api = await hass.async_add_executor_job(MullvadAPI)
            return api.data

    coordinator = update_coordinator.DataUpdateCoordinator(
        hass,
        logging.getLogger(__name__),
        name=DOMAIN,
        update_method=async_get_mullvad_api_data,
        update_interval=timedelta(minutes=1),
    )
    await coordinator.async_refresh()

    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    hass.data[DOMAIN] = coordinator

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
        del hass.data[DOMAIN]

    return unload_ok
