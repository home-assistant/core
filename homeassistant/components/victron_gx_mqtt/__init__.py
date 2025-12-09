"""The victron_mqtt integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.const import Platform

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

from .hub import Hub

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
]

type VictronGxConfigEntry = ConfigEntry[Hub]


async def _update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    _LOGGER.info("Options for victron_mqtt have been updated - applying changes")
    # Reload the integration to apply changes
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_entry(hass: HomeAssistant, entry: VictronGxConfigEntry) -> bool:
    """Set up victronvenus from a config entry."""
    _LOGGER.debug("async_setup_entry called for entry: %s", entry.entry_id)

    hub = Hub(hass, entry)
    entry.runtime_data = hub

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # All platforms should be set up before starting the hub
    try:
        await hub.start()
    except Exception as exc:
        _LOGGER.error(
            "Failure: hub.start() failed for entry %s: %s", entry.entry_id, exc
        )
        # Clean up partial setup to avoid double setup issues
        await async_unload_entry(hass, entry)
        raise

    # Register the update listener
    entry.async_on_unload(entry.add_update_listener(_update_listener))

    _LOGGER.debug("sync_setup_entry completed for entry: %s", entry.entry_id)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("async_unload_entry called for entry: %s", entry.entry_id)
    hub: Hub = entry.runtime_data
    if hub is not None:
        await hub.stop()

    await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    hub.unregister_all_new_metric_callbacks()

    return True
