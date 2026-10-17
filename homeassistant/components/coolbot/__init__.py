"""The CoolBot Pro integration.

Read-only. Nothing in this integration writes to a device.
"""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import CoolbotConfigEntry, CoolbotCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: CoolbotConfigEntry) -> bool:
    """Set up CoolBot Pro from a config entry."""
    coordinator = CoolbotCoordinator(hass, entry)
    try:
        await coordinator.async_config_entry_first_refresh()
    except BaseException:
        # runtime_data is never assigned, so no unload path can reach the socket
        # the first refresh already opened. BaseException, because the
        # coordinator re-raises an active CancelledError: a reload or shutdown
        # cancelling setup mid-refresh would bypass a narrower handler and leak
        # the socket.
        await coordinator.async_shutdown()
        raise
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: CoolbotConfigEntry) -> bool:
    """Unload a config entry and close its socket."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.async_shutdown()
    return unloaded
