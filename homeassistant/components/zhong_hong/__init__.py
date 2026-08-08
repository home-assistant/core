"""The ZhongHong HVAC integration."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import ZhongHongConfigEntry, ZhongHongCoordinator

PLATFORMS: list[Platform] = [Platform.CLIMATE]


async def async_setup_entry(hass: HomeAssistant, entry: ZhongHongConfigEntry) -> bool:
    """Set up ZhongHong from a config entry."""
    coordinator = ZhongHongCoordinator(hass, entry)
    # Discovery and the listener thread are started from the coordinator's
    # _async_setup, so a failure here leaves nothing behind: the coordinator
    # registers its own shutdown against the entry.
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ZhongHongConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
