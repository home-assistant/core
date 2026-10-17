"""The De Lijn integration."""

import asyncio

from pydelijn import DeLijnClient

from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import SUBENTRY_TYPE_STOP
from .coordinator import DeLijnConfigEntry, DeLijnCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: DeLijnConfigEntry) -> bool:
    """Set up De Lijn from a config entry."""
    client = DeLijnClient(entry.data[CONF_API_KEY], async_get_clientsession(hass))

    coordinators = {
        subentry_id: DeLijnCoordinator(hass, entry, subentry, client)
        for subentry_id, subentry in entry.subentries.items()
        if subentry.subentry_type == SUBENTRY_TYPE_STOP
    }

    await asyncio.gather(
        *(
            coordinator.async_config_entry_first_refresh()
            for coordinator in coordinators.values()
        )
    )

    entry.runtime_data = coordinators
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_update_listener(hass: HomeAssistant, entry: DeLijnConfigEntry) -> None:
    """Reload the entry when its stop subentries change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: DeLijnConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
