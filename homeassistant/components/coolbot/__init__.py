"""The CoolBot Pro integration.

Read-only. Nothing in this integration writes to a device.
"""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN
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


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: CoolbotConfigEntry, device_entry: dr.AnyDeviceEntry
) -> bool:
    """Allow deleting a device that the account no longer reports.

    Devices are enumerated from the account profile, so one that still appears
    there would just be recreated; only genuinely gone devices may be removed.
    """
    coordinator = entry.runtime_data
    identifiers = {
        identifier
        for domain, identifier in device_entry.identifiers
        if domain == DOMAIN
    }
    if any(identifier in coordinator.data for identifier in identifiers):
        return False

    # The entities are deleted along with the device, so drop the record of
    # them; if this cooler is added to the account again, its entities have to
    # be created afresh.
    for identifier in identifiers:
        coordinator.forget_device(identifier)
    return True
