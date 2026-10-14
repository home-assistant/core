"""The Gree Climate integration."""

from datetime import timedelta
import logging

from greeclimate.exceptions import DeviceNotBoundError, DeviceTimeoutError

from homeassistant.components.network import async_get_ipv4_broadcast_addresses
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_IP_ADDRESS, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.event import async_track_time_interval

from .const import DISCOVERY_SCAN_INTERVAL, DOMAIN
from .coordinator import (
    DeviceDataUpdateCoordinator,
    DiscoveryService,
    GreeConfigEntry,
    GreeRuntimeData,
    async_create_and_bind_device,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.CLIMATE, Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: GreeConfigEntry) -> bool:
    """Set up Gree Climate from a config entry."""
    if CONF_IP_ADDRESS in entry.data:
        ip_address = entry.data[CONF_IP_ADDRESS]
        try:
            device = await async_create_and_bind_device(ip_address)
        except (DeviceNotBoundError, DeviceTimeoutError, OSError) as err:
            raise ConfigEntryNotReady(
                f"Unable to connect to Gree device at {ip_address}"
            ) from err
        if device.device_info.mac != entry.unique_id:
            raise ConfigEntryNotReady(
                f"Gree device at {ip_address} has MAC {device.device_info.mac},"
                f" expected {entry.unique_id}"
            )
        coordinator = DeviceDataUpdateCoordinator(hass, entry, device)
        await coordinator.async_config_entry_first_refresh()

        # Take the device over from a discovery entry, keeping its device and
        # entity registry entries so area, name and history are preserved.
        for other_entry in hass.config_entries.async_entries(DOMAIN):
            if CONF_IP_ADDRESS in other_entry.data:
                continue
            if other_entry.state is ConfigEntryState.LOADED and any(
                other.device.device_info.mac == device.device_info.mac
                for other in other_entry.runtime_data.coordinators
            ):
                # Reload so the discovery entry drops the device.
                await hass.config_entries.async_reload(other_entry.entry_id)
            _async_move_device(
                hass, device.device_info.mac, other_entry.entry_id, entry.entry_id
            )
        entry.runtime_data = GreeRuntimeData(
            discovery_service=None, coordinators=[coordinator]
        )
    else:
        gree_discovery = DiscoveryService(hass, entry)
        entry.runtime_data = GreeRuntimeData(
            discovery_service=gree_discovery, coordinators=[]
        )

        async def _async_scan_update(_=None):
            bcast_addr = list(await async_get_ipv4_broadcast_addresses(hass))
            await gree_discovery.discovery.scan(0, bcast_ifaces=bcast_addr)

        _LOGGER.debug("Scanning network for Gree devices")
        await _async_scan_update()

        entry.async_on_unload(
            async_track_time_interval(
                hass, _async_scan_update, timedelta(seconds=DISCOVERY_SCAN_INTERVAL)
            )
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: GreeConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok and CONF_IP_ADDRESS in entry.data and entry.disabled_by is not None:
        _async_hand_device_to_discovery(hass, entry)
    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: GreeConfigEntry) -> None:
    """Handle removal of a config entry."""
    if CONF_IP_ADDRESS in entry.data:
        _async_hand_device_to_discovery(hass, entry)


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: GreeConfigEntry, device_entry: dr.AnyDeviceEntry
) -> bool:
    """Allow removing a device that the config entry no longer sets up."""
    if config_entry.state is not ConfigEntryState.LOADED:
        return True
    return not any(
        (DOMAIN, coordinator.device.device_info.mac) in device_entry.identifiers
        for coordinator in config_entry.runtime_data.coordinators
    )


@callback
def _async_hand_device_to_discovery(
    hass: HomeAssistant, entry: GreeConfigEntry
) -> None:
    """Give the device of a static IP entry back to a loaded discovery entry."""
    assert entry.unique_id is not None
    for other_entry in hass.config_entries.async_loaded_entries(DOMAIN):
        if other_entry.runtime_data.discovery_service is not None:
            _async_move_device(
                hass, entry.unique_id, entry.entry_id, other_entry.entry_id
            )
            hass.config_entries.async_schedule_reload(other_entry.entry_id)


@callback
def _async_move_device(
    hass: HomeAssistant, mac: str, from_entry_id: str, to_entry_id: str
) -> None:
    """Move a device and its entities from one config entry to another."""
    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, mac), from_entry_id
    )
    if device is None or (
        device_registry.async_get_device_by_identifier((DOMAIN, mac), to_entry_id)
        is not None
    ):
        return
    # Move the entities first, moving the device removes entities of the old entry.
    entity_registry = er.async_get(hass)
    for entity in er.async_entries_for_device(
        entity_registry, device.id, include_disabled_entities=True
    ):
        if entity.config_entry_id == from_entry_id:
            entity_registry.async_update_entity(
                entity.entity_id, config_entry_id=to_entry_id
            )
    device_registry.async_update_device(device.id, new_config_entry_id=to_entry_id)
