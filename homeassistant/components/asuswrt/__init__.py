"""Support for ASUSWRT devices."""

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import AnyDeviceEntry

from .router import AsusWrtRouter, get_device_identifier

PLATFORMS = [Platform.DEVICE_TRACKER, Platform.SENSOR]

type AsusWrtConfigEntry = ConfigEntry[AsusWrtRouter]


async def async_setup_entry(hass: HomeAssistant, entry: AsusWrtConfigEntry) -> None:
    """Set up AsusWrt platform."""

    router = AsusWrtRouter(hass, entry)
    await router.setup()

    router.async_on_close(entry.add_update_listener(update_listener))

    async def async_close_connection(event: Event) -> None:
        """Close AsusWrt connection on HA Stop."""
        await router.close()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_close_connection)
    )

    entry.runtime_data = router

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: AsusWrtConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
    router = entry.runtime_data
    await router.close()


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: AsusWrtConfigEntry, device_entry: AnyDeviceEntry
) -> bool:
    """Remove a client device which is not connected to the router."""
    if not isinstance(device_entry, dr.DeviceEntry):
        # This integration does not create child devices.
        return False
    if get_device_identifier(config_entry) in device_entry.identifiers:
        return False
    # Clients are restored from trackers, which are removed with the device
    if config_entry.state is not ConfigEntryState.LOADED:
        return True
    router = config_entry.runtime_data
    macs = {
        mac
        for connection_type, mac in device_entry.connections
        if connection_type == dr.CONNECTION_NETWORK_MAC
    }
    if any((device := router.devices.get(mac)) and device.is_connected for mac in macs):
        return False
    for mac in macs:
        router.async_forget_device(mac)
    return True


async def update_listener(hass: HomeAssistant, entry: AsusWrtConfigEntry) -> None:
    """Reload when the connection data or options requiring a reload change."""
    router = entry.runtime_data

    if router.update_options(entry.options) or router.data_changed(entry.data):
        await hass.config_entries.async_reload(entry.entry_id)
