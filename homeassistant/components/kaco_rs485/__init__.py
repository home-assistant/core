"""KACO RS485 integration."""

from homeassistant.const import CONF_PORT, Platform
from homeassistant.core import HomeAssistant

from .coordinator import KacoRs485ConfigEntry, KacoRs485Coordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: KacoRs485ConfigEntry) -> bool:
    """Set up KACO RS485 from a config entry."""
    coordinator = KacoRs485Coordinator(hass, entry, port=entry.data[CONF_PORT])

    # A failed setup must still release the port: two masters corrupt the bus.
    entry.async_on_unload(coordinator.async_close)

    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: KacoRs485ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
