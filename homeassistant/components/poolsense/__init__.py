"""The PoolSense integration."""
import asyncio
from datetime import timedelta
import logging

import async_timeout
from poolsense import PoolSense
from poolsense.exceptions import PoolSenseError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client, update_coordinator
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import DOMAIN

PLATFORMS = ["sensor"]

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the PoolSense component."""
    # Make sure coordinator is initialized.
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up PoolSense from a config entry."""
    poolsense = PoolSense()
    auth_valid = await poolsense.test_poolsense_credentials(
        aiohttp_client.async_get_clientsession(hass),
        entry.data[CONF_EMAIL],
        entry.data[CONF_PASSWORD],
    )

    if not auth_valid:
        _LOGGER.error("Invalid authentication")
        return False

    coordinator = await get_coordinator(hass, entry)

    await hass.data[DOMAIN][entry.entry_id].async_refresh()

    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    hass.data[DOMAIN][entry.entry_id] = coordinator

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

    return unload_ok


async def get_coordinator(hass, entry):
    """Get the data update coordinator."""

    async def async_get_data():
        _LOGGER.info("Run query to server")
        poolsense = PoolSense()
        return_data = {}
        with async_timeout.timeout(10):
            try:
                return_data = await poolsense.get_poolsense_data(
                    aiohttp_client.async_get_clientsession(hass),
                    entry.data[CONF_EMAIL],
                    entry.data[CONF_PASSWORD],
                )
            except (PoolSenseError) as error:
                raise UpdateFailed(error)

        return return_data

    return update_coordinator.DataUpdateCoordinator(
        hass,
        logging.getLogger(__name__),
        name=DOMAIN,
        update_method=async_get_data,
        update_interval=timedelta(hours=1),
    )
