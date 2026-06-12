"""The Midea ccm15 AC Controller integration."""

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, Platform
from homeassistant.core import HomeAssistant

from .const import CONF_MAX_TEMP, CONF_MIN_TEMP, DEFAULT_MAX_TEMP, DEFAULT_MIN_TEMP
from .coordinator import CCM15ConfigEntry, CCM15Coordinator

PLATFORMS: list[Platform] = [Platform.CLIMATE]


async def async_setup_entry(hass: HomeAssistant, entry: CCM15ConfigEntry) -> bool:
    """Set up Midea ccm15 AC Controller from a config entry."""
    coordinator = CCM15Coordinator(
        hass,
        entry,
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        entry.data.get(CONF_PASSWORD) or None,
        entry.data.get(CONF_MIN_TEMP, DEFAULT_MIN_TEMP),
        entry.data.get(CONF_MAX_TEMP, DEFAULT_MAX_TEMP),
    )
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: CCM15ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
