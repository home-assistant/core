"""Initializes the uhoo api client and setup needed for the devices."""

from aiodns.error import DNSError
from aiohttp.client_exceptions import ClientConnectionError
from uhooapi import Client
from uhooapi.errors import UhooError, UnauthorizedError

from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import PLATFORMS
from .coordinator import UhooConfigEntry, UhooDataUpdateCoordinator


async def async_setup_entry(hass: HomeAssistant, config_entry: UhooConfigEntry) -> bool:
    """Set up uHoo integration from a config entry."""

    # get api key and session from configuration
    api_key = config_entry.data[CONF_API_KEY]
    session = async_get_clientsession(hass)
    client = Client(api_key, session, debug=False)
    coordinator = UhooDataUpdateCoordinator(hass, client=client, entry=config_entry)

    try:
        await client.login()
        await client.setup_devices()
    except (ClientConnectionError, DNSError) as err:
        raise ConfigEntryNotReady(f"Cannot connect to uHoo servers: {err}") from err
    except UnauthorizedError as err:
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
