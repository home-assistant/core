"""The Zendure Smart Meter P1 integration."""

from zendure_p1 import ZendureP1Client

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import PLATFORMS
from .coordinator import ZendureP1Coordinator

type ZendureP1ConfigEntry = ConfigEntry[ZendureP1Coordinator]


async def async_setup_entry(hass: HomeAssistant, entry: ZendureP1ConfigEntry) -> bool:
    """Set up Zendure Smart Meter P1 from a config entry."""
    api = ZendureP1Client(entry.data[CONF_HOST])
    coordinator = ZendureP1Coordinator(hass, entry, api)
    entry.runtime_data = coordinator

    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady:
        await api.close()
        raise

    entry.async_on_unload(api.close)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_reload_entry(hass: HomeAssistant, entry: ZendureP1ConfigEntry) -> None:
    """Reload the config entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ZendureP1ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
