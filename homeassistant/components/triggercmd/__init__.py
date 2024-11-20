"""The TRIGGERcmd component."""

from __future__ import annotations

from triggercmd import client, ha

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_TOKEN

PLATFORMS = [
    Platform.SWITCH,
]

type TriggercmdConfigEntry = ConfigEntry[ha.Hub]


async def async_setup_entry(hass: HomeAssistant, entry: TriggercmdConfigEntry) -> bool:
    """Set up TRIGGERcmd from a config entry."""
    hub = ha.Hub(entry.data[CONF_TOKEN])

    status_code = await client.async_connection_test(entry.data[CONF_TOKEN])
    if status_code != 200:
        raise ConfigEntryNotReady

    entry.runtime_data = hub
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: TriggercmdConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
