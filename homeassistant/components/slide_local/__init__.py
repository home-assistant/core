"""Component for the Slide local API."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import SlideConfigEntry, SlideCoordinator

PLATFORMS = [Platform.BUTTON, Platform.COVER, Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: SlideConfigEntry) -> bool:
    """Set up the slide_local integration."""

    coordinator = SlideCoordinator(hass, entry)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: SlideConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
