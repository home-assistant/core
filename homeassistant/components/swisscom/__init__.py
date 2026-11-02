"""The Swisscom Internet-Box integration."""

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
    """Allow removing a client device which the Internet-Box no longer knows."""
    if not isinstance(device_entry, dr.DeviceEntry):
        # This integration does not create child devices.
        return False
    protected_macs = {
        dr.format_mac(device.phys_address)
        for device in entry.runtime_data.data.values()
    }
    if entry.unique_id:
        protected_macs.add(entry.unique_id)
    return not any(
        connection_type == dr.CONNECTION_NETWORK_MAC and mac in protected_macs
        for connection_type, mac in device_entry.connections
    )
