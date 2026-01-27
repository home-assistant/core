"""The victron_gx_mqtt integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant

from .hub import Hub

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
]

type VictronGxConfigEntry = ConfigEntry[Hub]


async def async_setup_entry(hass: HomeAssistant, entry: VictronGxConfigEntry) -> bool:
    """Set up victronvenus from a config entry."""
    _LOGGER.debug("async_setup_entry called for entry: %s", entry.entry_id)

    hub = Hub(hass, entry)
    entry.runtime_data = hub

    # All platforms should be set up before starting the hub
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await hub.start()

    # Register the update listener
    async def _update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
        _LOGGER.info("Options have been updated - applying changes")
        # Reload the integration to apply changes
        await hass.config_entries.async_reload(entry.entry_id)

    entry.async_on_unload(entry.add_update_listener(_update_listener))

    async def _async_stop(_: Event) -> None:
        await hub.stop()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_stop)
    )

    _LOGGER.debug("sync_setup_entry completed for entry: %s", entry.entry_id)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: VictronGxConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("async_unload_entry called for entry: %s", entry.entry_id)
    hub: Hub = entry.runtime_data
    assert isinstance(hub, Hub)
    await hub.stop()

    await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    hub.unregister_all_new_metric_callbacks()

    return True
