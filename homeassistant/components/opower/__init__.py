"""The Opower integration."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import OpowerConfigEntry, OpowerCoordinator
from .repairs import async_validate_negative_stats

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: OpowerConfigEntry) -> bool:
    """Set up Opower from a config entry."""
    coordinator = OpowerCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    # Run validation after first data load so that any automatic fixes
    # from statistics backfilling have been applied
    await async_validate_negative_stats(hass)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: OpowerConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
