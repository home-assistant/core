"""The Tailscale integration."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import TailscaleConfigEntry, TailscaleDataUpdateCoordinator

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: TailscaleConfigEntry) -> bool:
    """Set up Tailscale from a config entry."""
    coordinator = TailscaleDataUpdateCoordinator(hass, entry)

    # Cancels the OAuth access token refresh task, when one is scheduled.
    # Registered before the first refresh: async_unload_entry is not called
    # when setup fails, but on_unload callbacks are, so a failing setup (and
    # each subsequent retry) would otherwise leave a task alive until the
    # token expires.
    entry.async_on_unload(coordinator.tailscale.close)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: TailscaleConfigEntry) -> bool:
    """Unload Tailscale config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
