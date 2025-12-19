"""Imports for __init__.py."""

import asyncio

from uhooapi import Client
from uhooapi.errors import UhooError, UnauthorizedError

from homeassistant import core
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, LOGGER, PLATFORMS, STARTUP_MESSAGE
from .coordinator import UhooDataUpdateCoordinator


async def async_setup_entry(
    hass: core.HomeAssistant, config_entry: ConfigEntry
) -> bool:
    """Set up uHoo integration from a config entry."""
    if hass.data.get(DOMAIN) is None:
        hass.data.setdefault(DOMAIN, {})
        LOGGER.info(STARTUP_MESSAGE)

    # get api key and session from configuration
    api_key = config_entry.data.get(CONF_API_KEY)
    session = async_get_clientsession(hass)

    try:
        if api_key is None:
            raise ValueError("API key is required")
        client = Client(api_key, session, debug=True)
        await client.login()
        await client.setup_devices()
    except UnauthorizedError as err:
        LOGGER.error(f"Error: 401 Unauthorized error while logging in: {err}")
        return False
    except UhooError as err:
        raise ConfigEntryNotReady(err) from err

    coordinator = UhooDataUpdateCoordinator(hass, client=client)
    await coordinator.async_refresh()

    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    hass.data[DOMAIN][config_entry.entry_id] = coordinator
    config_entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: core.HomeAssistant, config_entry: ConfigEntry
) -> bool:
    """Handle removal of an entry."""
    coordinator = config_entry.runtime_data
    unloaded = all(
        await asyncio.gather(
            *(
                hass.config_entries.async_forward_entry_unload(config_entry, platform)
                for platform in PLATFORMS
                if platform in coordinator.platforms
            )
        )
    )

    # Clean up from hass.data
    if DOMAIN in hass.data and config_entry.entry_id in hass.data[DOMAIN]:
        hass.data[DOMAIN].pop(config_entry.entry_id)

    # If domain dict is now empty, remove it completely
    if DOMAIN in hass.data and not hass.data[DOMAIN]:
        hass.data.pop(DOMAIN)
    await hass.async_block_till_done()
    return unloaded
