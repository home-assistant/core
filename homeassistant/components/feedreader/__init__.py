"""Support for RSS/Atom feeds."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN
from .coordinator import FeedReaderConfigEntry, FeedReaderCoordinator, StoredData

CONF_URLS = "urls"

MY_KEY: HassKey[StoredData] = HassKey(DOMAIN)


async def async_setup_entry(hass: HomeAssistant, entry: FeedReaderConfigEntry) -> bool:
    """Set up Feedreader from a config entry."""
    storage = hass.data.setdefault(MY_KEY, StoredData(hass))
    if not storage.is_initialized:
        await storage.async_setup()

    coordinator = FeedReaderCoordinator(hass, entry, storage)

    await coordinator.async_setup()

    entry.runtime_data = coordinator

    # we need to setup event entities before the first coordinator data fetch
    # so that the event entities can already fetch the events during the first fetch
    await hass.config_entries.async_forward_entry_setups(entry, [Platform.EVENT])

    await coordinator.async_config_entry_first_refresh()

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: FeedReaderConfigEntry) -> bool:
    """Unload a config entry."""
    entries = hass.config_entries.async_entries(
        DOMAIN, include_disabled=False, include_ignore=False
    )
    # if this is the last entry, remove the storage
    if len(entries) == 1:
        hass.data.pop(MY_KEY)
    return await hass.config_entries.async_unload_platforms(entry, Platform.EVENT)


async def _async_update_listener(
    hass: HomeAssistant, entry: FeedReaderConfigEntry
) -> None:
    """Handle reconfiguration."""
    await hass.config_entries.async_reload(entry.entry_id)
