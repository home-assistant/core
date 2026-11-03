"""The Midea ccm15 AC Controller integration."""

from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant

from .coordinator import CCM15ConfigEntry, CCM15Coordinator

PLATFORMS: list[Platform] = [Platform.CLIMATE]


async def async_setup_entry(hass: HomeAssistant, entry: CCM15ConfigEntry) -> None:
    """Set up Midea ccm15 AC Controller from a config entry."""

    coordinator = CCM15Coordinator(
        hass,
        entry,
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
    )
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: CCM15ConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
