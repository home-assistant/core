"""Integration for BACnet building automation protocol."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.config_entries import SOURCE_INTEGRATION_DISCOVERY, ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, discovery_flow
from homeassistant.helpers.event import async_track_time_interval

from .bacnet_client import BACnetClient, resolve_interface_to_ip
from .const import (
    CONF_DEVICE_ADDRESS,
    CONF_DEVICE_ID,
    CONF_ENTRY_TYPE,
    CONF_HUB_ID,
    CONF_INTERFACE,
    DATA_CLIENT,
    DATA_DEVICES,
    DATA_HUB_ID,
    DISCOVERY_INTERVAL,
    DISCOVERY_TIMEOUT,
    DOMAIN,
    ENTRY_TYPE_DEVICE,
    ENTRY_TYPE_HUB,
)
from .coordinator import BACnetDeviceCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]


@dataclass
class BACnetHubRuntimeData:
    """Runtime data for a BACnet hub entry."""

    client: BACnetClient
    hub_device_id: str
    discovery_task: asyncio.Task[None] | None = None
    discovery_cancel: Callable[[], None] | None = None


@dataclass
class BACnetDeviceRuntimeData:
    """Runtime data for a BACnet device entry."""

    coordinator: BACnetDeviceCoordinator


type BACnetHubConfigEntry = ConfigEntry[BACnetHubRuntimeData]
type BACnetDeviceConfigEntry = ConfigEntry[BACnetDeviceRuntimeData]


async def _async_discover_devices(
    hass: HomeAssistant, hub_entry: BACnetHubConfigEntry
) -> None:
    """Discover BACnet devices and create discovery flows."""
    if not hub_entry.runtime_data:
        return

    client = hub_entry.runtime_data.client

    try:
        devices = await client.discover_devices(timeout=DISCOVERY_TIMEOUT)

        # Get existing devices to avoid duplicates
        existing_devices = {
            entry.unique_id
            for entry in hass.config_entries.async_entries(DOMAIN)
            if entry.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_DEVICE
        }

        # Create discovery flows for new devices
        for device in devices:
            device_unique_id = str(device.device_id)
            if device_unique_id not in existing_devices:
                # Build a descriptive title for the discovery card
                # Extract just the IP address without port for cleaner display
                ip_address = (
                    device.address.split(":")[0]
                    if ":" in device.address
                    else device.address
                )
                base_name = device.name or f"Device {device.device_id}"
                title = f"{base_name} ({ip_address})"

                if device.vendor_name and device.model_name:
                    subtitle = f"{device.vendor_name} {device.model_name}"
                elif device.vendor_name:
                    subtitle = device.vendor_name
                elif device.model_name:
                    subtitle = device.model_name
                else:
                    subtitle = "BACnet Device"

                # Create a discovery flow using the helper
                discovery_flow.async_create_flow(
                    hass,
                    DOMAIN,
                    context={
                        "source": SOURCE_INTEGRATION_DISCOVERY,
                        "unique_id": device_unique_id,
                        "title_placeholders": {
                            "name": title,
                            "model": subtitle,
                        },
                    },
                    data={
                        CONF_DEVICE_ID: device.device_id,
                        CONF_DEVICE_ADDRESS: device.address,
                        CONF_HUB_ID: hub_entry.entry_id,
                        "name": device.name,
                        "vendor_name": device.vendor_name,
                        "model_name": device.model_name,
                    },
                )

    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("Error during BACnet device discovery: %s", err)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up BACnet from a config entry."""
    # Initialize hass.data structure if needed
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault(DATA_DEVICES, set())

    entry_type = entry.data.get(CONF_ENTRY_TYPE, ENTRY_TYPE_DEVICE)

    if entry_type == ENTRY_TYPE_HUB:
        entry.runtime_data = await _async_setup_hub_entry(hass, entry)
    else:
        # Set runtime_data before forwarding platforms so platform setup
        # can access entry.runtime_data.coordinator
        entry.runtime_data = await _async_setup_device_entry(hass, entry)
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

        # Start background setup after platforms are ready
        entry.runtime_data.coordinator.start_background_setup()

        # Register options update listener
        entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def _async_setup_hub_entry(
    hass: HomeAssistant, entry: BACnetHubConfigEntry
) -> BACnetHubRuntimeData:
    """Set up a BACnet hub (client) config entry."""
    interface: str = entry.data[CONF_INTERFACE]

    # Resolve interface name to IP address
    listen_address = await resolve_interface_to_ip(interface)

    # Create BACnet client
    client = BACnetClient()
    try:
        await client.connect(listen_address)
    except Exception as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
            translation_placeholders={"error": str(err)},
        ) from err

    # Store client in hass.data
    hass.data[DOMAIN][DATA_CLIENT] = client

    # Register hub device in device registry
    # Use interface name for stable device ID (not IP which may change)
    hub_device_id = f"bacnet_client_{interface.replace('.', '_').replace(':', '_').replace('/', '_')}"
    device_registry = dr.async_get(hass)

    # Build device info for hub - show both interface and current IP
    if interface == listen_address:
        # Interface is already an IP or 0.0.0.0
        hub_name = f"BACnet Client ({interface})"
    else:
        # Show interface name with current IP
        hub_name = f"BACnet Client ({interface}: {listen_address})"

    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, hub_device_id)},
        name=hub_name,
        manufacturer="Home Assistant",
        model="BACnet/IP Client",
    )

    # Store hub ID in hass.data for device entries to reference
    hass.data[DOMAIN][DATA_HUB_ID] = entry.entry_id

    runtime_data = BACnetHubRuntimeData(
        client=client,
        hub_device_id=hub_device_id,
    )

    # Run initial device discovery (need to set runtime_data first for discovery to work)
    entry.runtime_data = runtime_data
    runtime_data.discovery_task = hass.async_create_task(
        _async_discover_devices(hass, entry)
    )

    # Set up periodic discovery
    async def _periodic_discovery(*_: Any) -> None:
        """Periodic discovery wrapper."""
        await _async_discover_devices(hass, entry)

    runtime_data.discovery_cancel = async_track_time_interval(
        hass, _periodic_discovery, DISCOVERY_INTERVAL
    )

    return runtime_data


async def _async_setup_device_entry(
    hass: HomeAssistant, entry: BACnetDeviceConfigEntry
) -> BACnetDeviceRuntimeData:
    """Set up a BACnet device config entry."""
    device_id: int = entry.data[CONF_DEVICE_ID]
    device_address: str = entry.data[CONF_DEVICE_ADDRESS]
    hub_entry_id: str = entry.data[CONF_HUB_ID]

    # Get client from parent hub
    hub_entry = hass.config_entries.async_get_entry(hub_entry_id)
    if (
        not hub_entry
        or not hasattr(hub_entry, "runtime_data")
        or not hub_entry.runtime_data
    ):
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="hub_not_ready",
            translation_placeholders={"hub_id": hub_entry_id},
        )
    client = hub_entry.runtime_data.client

    # Discover device info
    try:
        devices = await client.discover_devices(
            timeout=10,
            low_limit=device_id,
            high_limit=device_id,
        )
    except Exception as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="device_not_found",
            translation_placeholders={
                "device_id": str(device_id),
                "error": str(err),
            },
        ) from err

    if not devices:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="device_offline",
            translation_placeholders={"device_id": str(device_id)},
        )

    device_info = devices[0]
    device_info.address = device_address

    # Create coordinator
    coordinator = BACnetDeviceCoordinator(hass, entry, client, device_info)

    # Do first refresh to discover objects (fast, ~2 seconds)
    await coordinator.async_config_entry_first_refresh()

    runtime_data = BACnetDeviceRuntimeData(coordinator=coordinator)

    # Track this device
    hass.data[DOMAIN][DATA_DEVICES].add(entry.entry_id)

    return runtime_data


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the config entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a BACnet config entry."""
    entry_type = entry.data.get(CONF_ENTRY_TYPE, ENTRY_TYPE_DEVICE)

    if entry_type == ENTRY_TYPE_HUB:
        return await _async_unload_hub_entry(hass, entry)
    return await _async_unload_device_entry(hass, entry)


async def _async_unload_hub_entry(
    hass: HomeAssistant, entry: BACnetHubConfigEntry
) -> bool:
    """Unload a BACnet hub entry."""
    runtime_data = entry.runtime_data

    # Cancel periodic discovery
    if runtime_data.discovery_cancel:
        runtime_data.discovery_cancel()

    # Cancel any ongoing discovery task
    if runtime_data.discovery_task and not runtime_data.discovery_task.done():
        runtime_data.discovery_task.cancel()

    # Disconnect client
    await runtime_data.client.disconnect()

    # Remove from hass.data
    hass.data[DOMAIN].pop(DATA_CLIENT, None)
    hass.data[DOMAIN].pop(DATA_HUB_ID, None)

    return True


async def _async_unload_device_entry(
    hass: HomeAssistant, entry: BACnetDeviceConfigEntry
) -> bool:
    """Unload a BACnet device entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        runtime_data = entry.runtime_data
        await runtime_data.coordinator.async_shutdown()

        # Remove this device from tracking
        hass.data[DOMAIN][DATA_DEVICES].discard(entry.entry_id)

    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle removal of an entry."""
    entry_type = entry.data.get(CONF_ENTRY_TYPE, ENTRY_TYPE_DEVICE)

    if entry_type == ENTRY_TYPE_HUB:
        # When hub is removed, remove all child devices
        device_entries = [
            e
            for e in hass.config_entries.async_entries(DOMAIN)
            if e.data.get(CONF_HUB_ID) == entry.entry_id
        ]
        for device_entry in device_entries:
            await hass.config_entries.async_remove(device_entry.entry_id)
