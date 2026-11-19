"""The Swisscom Internet-Box integration."""

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .coordinator import SwisscomConfigEntry, SwisscomDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.DEVICE_TRACKER]


async def async_setup_entry(hass: HomeAssistant, entry: SwisscomConfigEntry) -> None:
    """Set up Swisscom Internet-Box from a config entry."""
    coordinator = SwisscomDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: SwisscomConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: SwisscomConfigEntry, device_entry: dr.AnyDeviceEntry
) -> bool:
    """Allow removing a client device which is not currently connected.

    The device of the Internet-Box itself can't be removed.
    """
    if not isinstance(device_entry, dr.DeviceEntry):
        # This integration does not create child devices.
        return False
    macs = {
        mac
        for connection_type, mac in device_entry.connections
        if connection_type == dr.CONNECTION_NETWORK_MAC
    }
    if entry.unique_id in macs:
        return False
    # Without data from the Internet-Box, no client is known to be connected
    if entry.state is not ConfigEntryState.LOADED:
        return True
    return macs.isdisjoint(
        dr.format_mac(device.phys_address)
        for device in entry.runtime_data.data.values()
        if device.active
    )
