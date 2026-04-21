"""Support for Netgear routers."""

from __future__ import annotations

import logging

from homeassistant.const import CONF_PORT, CONF_SSL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import PLATFORMS
from .coordinator import (
    NetgearConfigEntry,
    NetgearFirmwareCoordinator,
    NetgearLinkCoordinator,
    NetgearRuntimeData,
    NetgearSpeedTestCoordinator,
    NetgearTrackerCoordinator,
    NetgearTrafficMeterCoordinator,
    NetgearUtilizationCoordinator,
)
from .errors import CannotLoginException
from .router import NetgearRouter

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: NetgearConfigEntry) -> bool:
    """Set up Netgear component."""
    router = NetgearRouter(hass, entry)
    try:
        if not await router.async_setup():
            raise ConfigEntryNotReady
    except CannotLoginException as ex:
        raise ConfigEntryNotReady from ex

    port = entry.data.get(CONF_PORT)
    ssl = entry.data.get(CONF_SSL)
    if port != router.port or ssl != router.ssl:
        data = {**entry.data, CONF_PORT: router.port, CONF_SSL: router.ssl}
        hass.config_entries.async_update_entry(entry, data=data)
        _LOGGER.warning(
            (
                "Netgear port-SSL combination updated from (%i, %r) to (%i, %r), "
                "this should only occur after a firmware update"
            ),
            port,
            ssl,
            router.port,
            router.ssl,
        )

    # Create update coordinators
    coordinator_tracker = NetgearTrackerCoordinator(hass, router, entry)
    coordinator_traffic_meter = NetgearTrafficMeterCoordinator(hass, router, entry)
    coordinator_speed_test = NetgearSpeedTestCoordinator(hass, router, entry)
    coordinator_firmware = NetgearFirmwareCoordinator(hass, router, entry)
    coordinator_utilization = NetgearUtilizationCoordinator(hass, router, entry)
    coordinator_link = NetgearLinkCoordinator(hass, router, entry)

    if router.track_devices:
        await coordinator_tracker.async_config_entry_first_refresh()
    await coordinator_traffic_meter.async_config_entry_first_refresh()
    await coordinator_firmware.async_config_entry_first_refresh()
    await coordinator_utilization.async_config_entry_first_refresh()
    await coordinator_link.async_config_entry_first_refresh()

    entry.runtime_data = NetgearRuntimeData(
        router=router,
        coordinator_tracker=coordinator_tracker,
        coordinator_traffic=coordinator_traffic_meter,
        coordinator_speed=coordinator_speed_test,
        coordinator_firmware=coordinator_firmware,
        coordinator_utilization=coordinator_utilization,
        coordinator_link=coordinator_link,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: NetgearConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    router = entry.runtime_data.router

    if not router.track_devices:
        router_id = None
        # Remove devices that are no longer tracked
        device_registry = dr.async_get(hass)
        devices = dr.async_entries_for_config_entry(device_registry, entry.entry_id)
        for device_entry in devices:
            if device_entry.via_device_id is None:
                router_id = device_entry.id
                continue  # do not remove the router itself
            device_registry.async_update_device(
                device_entry.id, remove_config_entry_id=entry.entry_id
            )
        # Remove entities that are no longer tracked
        entity_registry = er.async_get(hass)
        entries = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
        for entity_entry in entries:
            if entity_entry.device_id is not router_id:
                entity_registry.async_remove(entity_entry.entity_id)

    return unload_ok


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: NetgearConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Remove a device from a config entry."""
    router = config_entry.runtime_data.router

    device_mac = None
    for connection in device_entry.connections:
        if connection[0] == dr.CONNECTION_NETWORK_MAC:
            device_mac = connection[1]
            break

    if device_mac is None:
        return False

    if device_mac not in router.devices:
        return True

    return not router.devices[device_mac]["active"]
