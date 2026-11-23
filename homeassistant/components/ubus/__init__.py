"""The OpenWrt (ubus) integration."""
# pylint: disable=home-assistant-use-runtime-data  # Uses legacy hass.data[DOMAIN] pattern

from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import AnyDeviceEntry
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import DOMAIN, SIGNAL_CLIENTS_UPDATED
from .coordinator import UbusConfigEntry, UbusDataUpdateCoordinator, UbusSharedState

PLATFORMS = [Platform.DEVICE_TRACKER]


async def async_setup_entry(hass: HomeAssistant, entry: UbusConfigEntry) -> None:
    """Set up ubus from a config entry."""
    hass.data.setdefault(DOMAIN, UbusSharedState())
    coordinator = UbusDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: UbusConfigEntry) -> None:
    """Unload a config entry."""
    # The platforms are unloaded first, so the entry's trackers are gone
    # before its client reports are released and the remaining trackers
    # are signalled.
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
    entry.runtime_data.async_unload()
    if not hass.config_entries.async_entries(DOMAIN):
        hass.data.pop(DOMAIN, None)


async def async_remove_entry(hass: HomeAssistant, entry: UbusConfigEntry) -> None:
    """Hand this entry's trackers to a remaining router before cleanup.

    The platforms are unloaded first, so the entry no longer hosts its
    trackers, but their registry entries survive until the config entry
    cleanup. Reparenting them here keeps the entry's clients tracked,
    including clients no remaining router currently sees.
    """
    remaining = hass.config_entries.async_entries(DOMAIN)
    if not remaining or (shared := hass.data.get(DOMAIN)) is None:
        return
    target = remaining[0]
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)
    for registry_entry in er.async_entries_for_config_entry(
        entity_registry, entry.entry_id
    ):
        if (
            registry_entry.domain != DEVICE_TRACKER_DOMAIN
            or registry_entry.platform != DOMAIN
            or registry_entry.unique_id is None
        ):
            continue
        mac = registry_entry.unique_id
        # Re-home the tracker before its device: moving a device to another
        # config entry deletes the registry entries of the old entry linked
        # to it.
        entity_registry.async_update_entity(
            registry_entry.entity_id, config_entry_id=target.entry_id
        )
        if (
            device := device_registry.async_get_device_by_connection(
                (dr.CONNECTION_NETWORK_MAC, mac), entry.entry_id
            )
        ) is not None:
            target_device = device_registry.async_get_device_by_connection(
                (dr.CONNECTION_NETWORK_MAC, mac), target.entry_id
            )
            if target_device is not None:
                entity_registry.async_update_entity(
                    registry_entry.entity_id, device_id=target_device.id
                )
            else:
                device_registry.async_update_device(
                    device.id, new_config_entry_id=target.entry_id
                )
    shared.remove_entry(entry.entry_id)
    async_dispatcher_send(hass, SIGNAL_CLIENTS_UPDATED)


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: UbusConfigEntry, device_entry: AnyDeviceEntry
) -> bool:
    """Allow removing a client device which is not currently connected."""
    if not isinstance(device_entry, dr.DeviceEntry):
        # This integration does not create child devices.
        return False
    if config_entry.state is not ConfigEntryState.LOADED:
        return True
    shared: UbusSharedState = hass.data[DOMAIN]
    return all(
        shared.latest_stamp(dr.format_mac(connection)) is None
        for connection_type, connection in device_entry.connections
        if connection_type == dr.CONNECTION_NETWORK_MAC
    )
