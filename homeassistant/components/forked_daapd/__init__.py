"""The forked_daapd component."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import ForkedDaapdConfigEntry

PLATFORMS = [Platform.MEDIA_PLAYER]


async def async_setup_entry(hass: HomeAssistant, entry: ForkedDaapdConfigEntry) -> bool:
    """Set up forked-daapd from a config entry by forwarding to platform."""
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: ForkedDaapdConfigEntry
) -> bool:
    """Remove forked-daapd component."""
    status = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if status and hasattr(entry, "runtime_data"):
        if websocket_handler := entry.runtime_data.websocket_handler:
            websocket_handler.cancel()
    return status
