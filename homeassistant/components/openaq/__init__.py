"""The OpenAQ integration."""

import asyncio

from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant

from .const import SUBENTRY_TYPE_LOCATION
from .coordinator import (
    OpenAQConfigEntry,
    OpenAQDataUpdateCoordinator,
    OpenAQRuntimeData,
    async_create_openaq_client,
)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: OpenAQConfigEntry) -> bool:
    """Set up OpenAQ from a config entry."""
    client = await async_create_openaq_client(hass, entry.data[CONF_API_KEY])
    coordinators: dict[str, OpenAQDataUpdateCoordinator] = {}

    for subentry in entry.get_subentries_of_type(SUBENTRY_TYPE_LOCATION):
        coordinators[subentry.subentry_id] = OpenAQDataUpdateCoordinator(
            hass, entry, subentry, client
        )

    try:
        await asyncio.gather(
            *(
                coordinator.async_config_entry_first_refresh()
                for coordinator in coordinators.values()
            )
        )
    except Exception:
        await client.close()
        raise

    entry.runtime_data = OpenAQRuntimeData(client=client, coordinators=coordinators)
    entry.async_on_unload(entry.add_update_listener(async_update_entry))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_update_entry(hass: HomeAssistant, entry: OpenAQConfigEntry) -> None:
    """Update the config entry."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: OpenAQConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok and (runtime_data := getattr(entry, "runtime_data", None)):
        await runtime_data.client.close()
    return unload_ok
