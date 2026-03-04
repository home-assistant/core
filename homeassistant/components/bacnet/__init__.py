"""Integration for BACnet building automation protocol."""

from __future__ import annotations

from dataclasses import dataclass, field

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .bacnet_client import BACnetClient, BACnetDeviceInfo, resolve_interface_to_ip
from .const import (
    CONF_DEVICE_ADDRESS,
    CONF_DEVICE_ID,
    CONF_DEVICE_INSTANCE,
    CONF_DEVICES,
    CONF_INTERFACE,
    DEVICE_INSTANCE_MIN,
    DISCOVERY_TIMEOUT,
    DOMAIN,
)
from .coordinator import BACnetDeviceCoordinator

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]


@dataclass
class BACnetHubRuntimeData:
    """Runtime data for a BACnet hub entry."""

    client: BACnetClient
    coordinators: dict[str, BACnetDeviceCoordinator] = field(default_factory=dict)
    discovered_devices: list[BACnetDeviceInfo] = field(default_factory=list)


type BACnetConfigEntry = ConfigEntry[BACnetHubRuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: BACnetConfigEntry) -> bool:
    """Set up BACnet from a config entry."""
    interface: str = entry.data[CONF_INTERFACE]

    # Resolve interface name to IP address
    listen_address = await resolve_interface_to_ip(interface)

    # Create BACnet client with persisted device instance
    device_instance: int = entry.data.get(CONF_DEVICE_INSTANCE, DEVICE_INSTANCE_MIN)
    client = BACnetClient()
    try:
        await client.connect(listen_address, device_instance)
    except Exception as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
            translation_placeholders={"error": str(err)},
        ) from err

    runtime_data = BACnetHubRuntimeData(
        client=client,
    )
    entry.runtime_data = runtime_data

    # Set up coordinators for each configured device (skip offline devices)
    devices_config: dict[str, dict] = entry.data.get(CONF_DEVICES, {})
    for device_key, device_config in devices_config.items():
        device_id: int = device_config[CONF_DEVICE_ID]
        device_address: str = device_config[CONF_DEVICE_ADDRESS]

        # Discover device info — skip this device if offline
        try:
            devices = await client.discover_devices(
                timeout=10,
                low_limit=device_id,
                high_limit=device_id,
            )
        except Exception:  # noqa: BLE001
            continue

        if not devices:
            continue

        device_info = devices[0]
        device_info.address = device_address

        # Create coordinator
        coordinator = BACnetDeviceCoordinator(
            hass, entry, device_config, client, device_info
        )

        # Do first refresh to discover objects
        await coordinator.async_config_entry_first_refresh()

        runtime_data.coordinators[device_key] = coordinator

    # Forward platform setup
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Start background setup for each coordinator
    for coordinator in runtime_data.coordinators.values():
        coordinator.start_background_setup()

    # Register update listener for reload when devices are added
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))

    # Discover devices in the background and show them in the Discovered panel
    entry.async_create_background_task(
        hass,
        _async_discover_devices(hass, entry),
        name=f"BACnet device discovery {entry.entry_id}",
    )

    return True


async def _async_discover_devices(
    hass: HomeAssistant, entry: BACnetConfigEntry
) -> None:
    """Discover BACnet devices and fire discovery flows for new ones."""
    client = entry.runtime_data.client
    try:
        devices = await client.discover_devices(timeout=DISCOVERY_TIMEOUT)
    except Exception:  # noqa: BLE001
        return

    if not devices:
        return

    # Filter out already-configured devices
    existing_device_ids = {
        dc.get(CONF_DEVICE_ID) for dc in entry.data.get(CONF_DEVICES, {}).values()
    }

    new_devices = [d for d in devices if d.device_id not in existing_device_ids]
    entry.runtime_data.discovered_devices = new_devices

    # Fire discovery flows so new devices appear in the "Discovered" panel
    for device in new_devices:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": "discovery"},
                data={
                    CONF_DEVICE_ID: device.device_id,
                    CONF_DEVICE_ADDRESS: device.address,
                    "device_name": device.name,
                    "vendor_name": device.vendor_name,
                    "model_name": device.model_name,
                    "hub_entry_id": entry.entry_id,
                },
            )
        )


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the config entry when data changes."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: BACnetConfigEntry) -> bool:
    """Unload a BACnet config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        # Shut down all coordinators
        for coordinator in entry.runtime_data.coordinators.values():
            await coordinator.async_shutdown()

        # Disconnect client
        await entry.runtime_data.client.disconnect()

    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Clean up when a BACnet hub entry is removed."""
    from .config_flow import async_abort_discovery_flows_for_hub  # noqa: PLC0415

    async_abort_discovery_flows_for_hub(hass, entry.entry_id)
