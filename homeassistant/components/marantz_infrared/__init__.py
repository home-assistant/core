"""Marantz IR Remote integration for Home Assistant."""

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

PLATFORMS = [Platform.BUTTON, Platform.MEDIA_PLAYER]


@dataclass
class MarantzIrRuntimeData:
    """Runtime data for a Marantz IR config entry.

    The RC-5 toggle bit must alternate between distinct key presses so
    the receiver can distinguish a new press from a held-down repeat.
    The toggle is tracked at the device level (one value per config
    entry) so all entities of a config entry share it.
    """

    toggle: int = 0


type MarantzIrConfigEntry = ConfigEntry[MarantzIrRuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: MarantzIrConfigEntry) -> bool:
    """Set up Marantz IR from a config entry."""
    entry.runtime_data = MarantzIrRuntimeData()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: MarantzIrConfigEntry) -> bool:
    """Unload a Marantz IR config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
