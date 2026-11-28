"""The PiKVM integration."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import PiKVMConfigEntry, PiKVMDataUpdateCoordinator, create_client

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: PiKVMConfigEntry) -> None:
    """Set up PiKVM from a config entry."""
    coordinator = PiKVMDataUpdateCoordinator(
        hass, entry, create_client(hass, entry.data)
    )
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: PiKVMConfigEntry) -> None:
    """Unload a PiKVM config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
