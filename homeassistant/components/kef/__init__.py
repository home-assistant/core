"""The KEF Wireless Speakers component."""

import aiohttp
from pykefcontrol.kef_connector import KefAsyncConnector

from homeassistant.const import CONF_HOST, Platform
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import KefConfigEntry, KefCoordinator

PLATFORMS = [Platform.MEDIA_PLAYER]


async def async_setup_entry(hass, entry: KefConfigEntry) -> bool:
    """Set up KEF from a config entry."""
    host = entry.data[CONF_HOST]
    model = entry.data.get("model")
    session = async_get_clientsession(hass)
    connector = KefAsyncConnector(host, session=session, model=model)

    try:
        await connector.mac_address
    except (aiohttp.ClientError, TimeoutError, IndexError, KeyError) as err:
        raise ConfigEntryNotReady(f"Cannot connect to KEF speaker at {host}") from err

    coordinator = KefCoordinator(hass, entry, connector)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass, entry: KefConfigEntry) -> bool:
    """Unload a KEF config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
