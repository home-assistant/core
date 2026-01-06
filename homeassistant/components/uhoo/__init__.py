"""Imports for __init__.py."""

from uhooapi import Client
from uhooapi.errors import UhooError, UnauthorizedError

from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import LOGGER, PLATFORMS
from .coordinator import UhooConfigEntry, UhooDataUpdateCoordinator


async def async_setup_entry(hass: HomeAssistant, config_entry: UhooConfigEntry) -> bool:
    """Set up uHoo integration from a config entry."""

    # get api key and session from configuration
    api_key = config_entry.data[CONF_API_KEY]
    session = async_get_clientsession(hass)
    client = Client(api_key, session, debug=True)
    coordinator = UhooDataUpdateCoordinator(hass, client=client)

    try:
        await client.login()
        await client.setup_devices()
    except UnauthorizedError as err:
        LOGGER.error("Error: 401 Unauthorized error while logging in: %s", err)
        raise ConfigEntryError(f"Invalid API credentials: {err}") from err
    except UhooError as err:
        raise ConfigEntryNotReady(err) from err

    await coordinator.async_config_entry_first_refresh()
    config_entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, config_entry: UhooConfigEntry
) -> bool:
    """Handle removal of an entry."""
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)
