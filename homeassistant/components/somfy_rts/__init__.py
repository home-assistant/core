"""The Somfy RTS integration."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import CONF_ROLLING_CODE, DOMAIN, STORAGE_VERSION
from .entity import SomfyRTSConfigEntry, SomfyRTSData

PLATFORMS: list[Platform] = [Platform.COVER]


async def async_setup_entry(hass: HomeAssistant, entry: SomfyRTSConfigEntry) -> bool:
    """Set up Somfy RTS from a config entry."""
    store = Store(hass, STORAGE_VERSION, f"{DOMAIN}/{entry.entry_id}")
    stored = await store.async_load()
    entry_default = entry.data.get(CONF_ROLLING_CODE, 1)
    rolling_code = stored.get("rolling_code", entry_default) if isinstance(stored, dict) else entry_default
    entry.runtime_data = SomfyRTSData(store=store, rolling_code=rolling_code)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SomfyRTSConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
