"""Integration for IRM KMI weather."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError

from .const import PLATFORMS
from .types import IrmKmiConfigEntry, RuntimeData

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: IrmKmiConfigEntry) -> bool:
    """Set up this integration using UI."""
    entry.runtime_data = RuntimeData(hass, entry)

    # When integration is set up, set the logging level of the irm_kmi_api package to the same level to help debugging.
    logging.getLogger("irm_kmi_api").setLevel(_LOGGER.getEffectiveLevel())
    try:
        await entry.runtime_data.coordinator.async_config_entry_first_refresh()
    except ConfigEntryError:
        # This happens when the zone is out of Benelux (no forecast available there).
        # This should be caught by the config flow anyway.
        return False

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle removal of an entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_migrate_entry(_hass: HomeAssistant, _config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    # There are no previous versions of the config entry at this time.
    return True
