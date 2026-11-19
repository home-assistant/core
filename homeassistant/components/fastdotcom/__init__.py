"""Support for testing internet speed via Fast.com."""

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.start import async_at_started

from .const import PLATFORMS
from .coordinator import FastdotcomConfigEntry, FastdotcomDataUpdateCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: FastdotcomConfigEntry) -> None:
    """Set up Fast.com from a config entry."""
    coordinator = FastdotcomDataUpdateCoordinator(hass, entry)
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(
        entry,
        PLATFORMS,
    )

    async def _async_finish_startup(hass: HomeAssistant) -> None:
        """Run this only when HA has finished its startup."""
        if entry.state is ConfigEntryState.LOADED:
            await coordinator.async_refresh()
        else:
            await coordinator.async_config_entry_first_refresh()

    # Don't start a speedtest during startup, this will slow
    # down the overall startup dramatically
    async_at_started(hass, _async_finish_startup)


async def async_unload_entry(hass: HomeAssistant, entry: FastdotcomConfigEntry) -> None:
    """Unload Fast.com config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
