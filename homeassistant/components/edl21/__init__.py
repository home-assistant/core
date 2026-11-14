"""The edl21 component."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Set up EDL21 integration from a config entry."""

    async def _update_listener(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Handle options update."""
        await hass.config_entries.async_reload(config_entry.entry_id)

    config_entry.async_on_unload(config_entry.add_update_listener(_update_listener))
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(config_entry, PLATFORMS)
    if api := config_entry.runtime_data:
        await api.disconnect()
