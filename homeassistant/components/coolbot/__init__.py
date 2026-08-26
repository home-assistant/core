"""The CoolBot Pro integration.

Read-only. Nothing in this integration writes to a device.
"""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN
from .coordinator import CoolbotConfigEntry, CoolbotCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: CoolbotConfigEntry) -> bool:
    """Set up CoolBot Pro from a config entry."""
    coordinator = CoolbotCoordinator(hass, entry)
    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryAuthFailed, ConfigEntryNotReady:
        # The socket may already be open (for example when the account reports
        # no devices) and nothing else will close it once setup is abandoned.
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
    current = entry.runtime_data.data
    return not any(
        identifier in current
        for domain, identifier in device_entry.identifiers
        if domain == DOMAIN
    )
