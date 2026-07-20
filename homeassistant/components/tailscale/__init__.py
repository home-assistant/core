"""The Tailscale integration."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import TailscaleConfigEntry, TailscaleDataUpdateCoordinator

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: TailscaleConfigEntry) -> bool:
    """Set up Tailscale from a config entry."""
    coordinator = TailscaleDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: TailscaleConfigEntry) -> bool:
    """Unload Tailscale config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        # Cancels the OAuth access token refresh task, when one is scheduled.
        await entry.runtime_data.tailscale.close()
    return unload_ok
