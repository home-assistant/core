"""The Somfy RTS integration."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN, STORAGE_VERSION
from .entity import SomfyRTSConfigEntry, SomfyRTSData

PLATFORMS: list[Platform] = [Platform.BUTTON, Platform.COVER]


async def async_setup_entry(hass: HomeAssistant, entry: SomfyRTSConfigEntry) -> bool:
    """Set up Somfy RTS from a config entry."""
    store = Store(hass, STORAGE_VERSION, f"{DOMAIN}/{entry.entry_id}")
    stored = await store.async_load()
    rolling_code = stored["rolling_code"] if stored is not None else 1
    entry.runtime_data = SomfyRTSData(store=store, rolling_code=rolling_code)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SomfyRTSConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
