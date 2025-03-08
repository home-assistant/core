"""The nederlandse_spoorwegen component."""

import asyncio
from dataclasses import dataclass

import ns_api
from ns_api import RequestParametersError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed

PLATFORMS = [Platform.SENSOR]


@dataclass
class NederlandseSpoorwegenData:
    """Data structure for runtime data."""

    nsapi: ns_api.NSAPI


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up NS API as config entry."""

    try:
        nsapi = ns_api.NSAPI(entry.data[CONF_API_KEY])
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, nsapi.get_stations)
        entry.runtime_data = NederlandseSpoorwegenData(nsapi)
    except RequestParametersError as ex:
        raise ConfigEntryAuthFailed(
            "Could not insantiate the Nederlandse Spoorwegen API."
        ) from ex
    else:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def update_listener(hass, entry):
    """Handle update."""
    await hass.config_entries.async_reload(entry.entry_id)
