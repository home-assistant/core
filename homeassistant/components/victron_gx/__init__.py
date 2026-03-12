"""The victron_gx integration."""

from __future__ import annotations

import logging

from homeassistant.const import EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .hub import Hub, VictronGxConfigEntry

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
]


async def async_setup_entry(hass: HomeAssistant, entry: VictronGxConfigEntry) -> bool:
    """Set up victron_gx from a config entry."""
    _LOGGER.debug("async_setup_entry called for entry: %s", entry.entry_id)

    hub = Hub(hass, entry)
    entry.runtime_data = hub

    # All platforms should be set up before starting the hub
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    try:
        await hub.start()
    except ConfigEntryNotReady, ConfigEntryAuthFailed:
        await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
        hub.unregister_all_new_metric_callbacks()
        raise

    async def _async_stop(_: Event) -> None:
        await hub.stop()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_stop)
    )

    _LOGGER.debug("async_setup_entry completed for entry: %s", entry.entry_id)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: VictronGxConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("async_unload_entry called for entry: %s", entry.entry_id)
    hub: Hub | None = getattr(entry, "runtime_data", None)
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok and hub is not None:
        await hub.stop()
        hub.unregister_all_new_metric_callbacks()

    return unload_ok
