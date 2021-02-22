"""The kmtronic integration."""
import asyncio
from datetime import timedelta
import logging

import aiohttp
import async_timeout
from pykmtronic.auth import Auth
from pykmtronic.hub import KMTronicHubAPI
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryNotReady
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_HOSTNAME,
    CONF_PASSWORD,
    CONF_USERNAME,
    DATA_COORDINATOR,
    DATA_HOST,
    DATA_HUB,
    DOMAIN,
    MANUFACTURER,
)

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)

PLATFORMS = ["switch"]

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the kmtronic component."""
    hass.data[DOMAIN] = {}

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up kmtronic from a config entry."""

    session = aiohttp_client.async_get_clientsession(hass)
    auth = Auth(
        session,
        f"http://{entry.data[CONF_HOSTNAME]}",
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
    )
    hub = KMTronicHubAPI(auth)

    async def async_update_data():
        try:
            async with async_timeout.timeout(10):
                await hub.async_update_relays()
        except aiohttp.client_exceptions.ClientResponseError as err:
            raise UpdateFailed(f"Wrong credentials: {err}") from err
        except (
            asyncio.TimeoutError,
            aiohttp.client_exceptions.ClientConnectorError,
        ) as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{MANUFACTURER} {hub.name}",
        update_method=async_update_data,
        update_interval=timedelta(seconds=30),
    )
    await coordinator.async_refresh()
    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    hass.data[DOMAIN][entry.entry_id] = {
        DATA_HUB: hub,
        DATA_HOST: entry.data[DATA_HOST],
        DATA_COORDINATOR: coordinator,
    }

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
