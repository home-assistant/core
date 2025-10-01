"""The OpenRGB integration."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntry

from .const import DOMAIN
from .coordinator import OpenRGBConfigEntry, OpenRGBCoordinator

PLATFORMS: list[Platform] = [Platform.LIGHT]


async def _async_migrate_unique_ids(
    hass: HomeAssistant, entry: OpenRGBConfigEntry
) -> None:
    """Migrate unique IDs when MAC address changes."""
    migration_data = entry.data["_migrate_mac"]
    old_mac = migration_data["old"]
    new_mac = migration_data["new"]

    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    # Migrate server device
    old_server_device = device_registry.async_get_device(
        identifiers={(DOMAIN, old_mac)}
    )
    if old_server_device:
        device_registry.async_update_device(
            old_server_device.id,
            new_identifiers={(DOMAIN, new_mac)},
            new_connections={(dr.CONNECTION_NETWORK_MAC, new_mac)},
        )

    # Migrate all entity unique IDs by replacing old MAC with new MAC
    entities = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    for entity_entry in entities:
        if not entity_entry.unique_id.startswith(f"{old_mac}||"):
            continue

        new_unique_id = entity_entry.unique_id.replace(
            f"{old_mac}||", f"{new_mac}||", 1
        )
        entity_registry.async_update_entity(
            entity_entry.entity_id, new_unique_id=new_unique_id
        )

        # Also update the device identifiers and via_device
        if not entity_entry.device_id:
            continue

        device = device_registry.async_get(entity_entry.device_id)
        if not device:
            continue

        # Update device identifiers
        new_device_identifiers = set()
        for domain, identifier in device.identifiers:
            if domain == DOMAIN and identifier.startswith(f"{old_mac}||"):
                new_identifier = identifier.replace(f"{old_mac}||", f"{new_mac}||", 1)
                new_device_identifiers.add((domain, new_identifier))
            else:
                new_device_identifiers.add((domain, identifier))

        device_registry.async_update_device(
            device.id,
            new_identifiers=new_device_identifiers,
        )


def _setup_server_device_registry(
    hass: HomeAssistant, entry: OpenRGBConfigEntry, coordinator: OpenRGBCoordinator
):
    """Set up device registry for the OpenRGB SDK Server."""
    device_registry = dr.async_get(hass)

    # Create the parent OpenRGB SDK Server device
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, coordinator.mac)},
        connections={(dr.CONNECTION_NETWORK_MAC, coordinator.mac)},
        name=f"OpenRGB ({coordinator.mac})",
        model="OpenRGB SDK Server",
        manufacturer="OpenRGB",
        sw_version=coordinator.get_client_protocol_version(),
        entry_type=dr.DeviceEntryType.SERVICE,
    )


async def async_setup_entry(hass: HomeAssistant, entry: OpenRGBConfigEntry) -> bool:
    """Set up OpenRGB from a config entry."""
    # Migrate unique IDs if MAC address changed during reconfiguration
    if "_migrate_mac" in entry.data:
        await _async_migrate_unique_ids(hass, entry)
        # Remove the migration marker
        hass.config_entries.async_update_entry(
            entry,
            data={k: v for k, v in entry.data.items() if k != "_migrate_mac"},
        )

    coordinator = OpenRGBCoordinator(hass, entry)

    await coordinator.async_config_entry_first_refresh()

    _setup_server_device_registry(hass, entry, coordinator)

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: OpenRGBConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok and hasattr(entry, "runtime_data"):
        await entry.runtime_data.async_client_disconnect()

    return unload_ok


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: OpenRGBConfigEntry, device_entry: DeviceEntry
) -> bool:
    """Remove the config entry if the device is no longer connected."""
    coordinator = entry.runtime_data

    for domain, identifier in device_entry.identifiers:
        if domain != DOMAIN:
            continue

        # Block removal of the OpenRGB SDK Server device
        if identifier == coordinator.mac:
            return False

        # Block removal of the OpenRGB device if it is still connected
        if identifier in coordinator.data:
            return False

        return True

    # Not our device
    return True
