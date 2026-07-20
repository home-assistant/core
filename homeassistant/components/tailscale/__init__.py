"""The Tailscale integration."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed

from .const import CONF_OAUTH_CLIENT_ID
from .coordinator import TailscaleConfigEntry, TailscaleDataUpdateCoordinator

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: TailscaleConfigEntry) -> bool:
    """Set up Tailscale from a config entry."""
    if CONF_OAUTH_CLIENT_ID not in entry.data:
        # Entries created with a 90-day API access token migrate to a
        # non-expiring OAuth client through reauthentication.
        raise ConfigEntryAuthFailed(
            "Tailscale now authenticates with an OAuth client instead of an "
            "API access token"
        )

    coordinator = TailscaleDataUpdateCoordinator(hass, entry)

    # Registered before the first refresh: a failed setup does not call
    # async_unload_entry, but does run on_unload callbacks.
    entry.async_on_unload(coordinator.tailscale.close)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: TailscaleConfigEntry) -> bool:
    """Unload Tailscale config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
