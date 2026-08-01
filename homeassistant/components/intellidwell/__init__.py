"""The IntelliDwell Sprinkler Controller integration."""

import logging

from pyintellidwell import IntelliDwellClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import IntelliDwellCoordinator

_LOGGER = logging.getLogger(__name__)
PLATFORMS: list[Platform] = [Platform.SWITCH]

type IntelliDwellConfigEntry = ConfigEntry[IntelliDwellCoordinator]


async def async_setup_entry(
    hass: HomeAssistant, entry: IntelliDwellConfigEntry
) -> bool:
    """Set up IntelliDwell Sprinkler Controller from a config entry."""
    host = entry.data[CONF_HOST]
    session = async_get_clientsession(hass)

    client = IntelliDwellClient(host, session=session)

    coordinator = IntelliDwellCoordinator(hass, client, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: IntelliDwellConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
