"""The Nice G.O. integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import HomeAssistant

from .coordinator import NiceGOUpdateCoordinator

_LOGGER = logging.getLogger(__name__)
PLATFORMS: list[Platform] = [
    Platform.COVER,
    Platform.EVENT,
    Platform.LIGHT,
    Platform.SWITCH,
]

type NiceGOConfigEntry = ConfigEntry[NiceGOUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: NiceGOConfigEntry) -> bool:
    """Set up Nice G.O. from a config entry."""

    coordinator = NiceGOUpdateCoordinator(hass)
    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, coordinator.async_ha_stop)
    )

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    entry.async_create_background_task(
        hass,
        coordinator.client_listen(),
        "nice_go_websocket_task",
    )

    entry.async_on_unload(coordinator.unsubscribe)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: NiceGOConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.api.close()

    return unload_ok
