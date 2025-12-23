"""Imports for __init__.py."""

from uhooapi import Client
from uhooapi.errors import UhooError, UnauthorizedError

from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, LOGGER, PLATFORMS, UhooConfigEntry
from .coordinator import UhooDataUpdateCoordinator


async def async_setup_entry(hass: HomeAssistant, config_entry: UhooConfigEntry) -> bool:
    """Set up uHoo integration from a config entry."""
    coordinator = UhooDataUpdateCoordinator(hass, entry=config_entry)
    if hass.data.get(DOMAIN) is None:
        hass.data.setdefault(DOMAIN, {})

    # get api key and session from configuration
    api_key = config_entry.data.get(CONF_API_KEY)
    session = async_get_clientsession(hass)
    if api_key is None:
        raise ValueError("API key is required")

    try:
        client = Client(api_key, session, debug=True)
        await client.login()
        await client.setup_devices()
    except UnauthorizedError as err:
        LOGGER.error("Error: 401 Unauthorized error while logging in: %s", err)
        raise ConfigEntryError(f"Invalid API credentials: {err}") from err
    except UhooError as err:
        raise ConfigEntryNotReady(err) from err

    config_entry.runtime_data = client

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][config_entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, config_entry: UhooConfigEntry
) -> bool:
    """Handle removal of an entry."""
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)
