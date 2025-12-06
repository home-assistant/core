"""The ToneWinner AT-500 integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry  # noqa: F401 - used for type hints
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import ToneWinnerConfigEntry, ToneWinnerCoordinator

_PLATFORMS: list[Platform] = [Platform.MEDIA_PLAYER]


async def async_setup_entry(hass: HomeAssistant, entry: ToneWinnerConfigEntry) -> bool:
    """Set up ToneWinner AT-500 from a config entry."""
    coordinator = ToneWinnerCoordinator(hass, entry)

    # Setup coordinator
    await coordinator.async_setup()

    # Store coordinator in runtime_data
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ToneWinnerConfigEntry) -> bool:
    """Unload a config entry."""
    # Cleanup coordinator
    await entry.runtime_data.async_shutdown()

    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
