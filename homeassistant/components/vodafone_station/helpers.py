"""Vodafone Station helpers."""

from typing import Any

from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import _LOGGER


async def cleanup_device_tracker(
    hass: HomeAssistant, config_entry: ConfigEntry, devices: dict[str, Any]
) -> None:
    """Cleanup stale device tracker."""
    entity_reg: er.EntityRegistry = er.async_get(hass)

    entities_removed: bool = False

    device_hosts_macs: set[str] = set()
    device_hosts_names: set[str] = set()
    for mac, device_info in devices.items():
        device_hosts_macs.add(mac)
        device_hosts_names.add(device_info.device.name)

    for entry in er.async_entries_for_config_entry(entity_reg, config_entry.entry_id):
        if entry.domain != DEVICE_TRACKER_DOMAIN:
            continue
        entry_name = entry.name or entry.original_name
        entry_host = entry_name.partition(" ")[0] if entry_name else None
        entry_mac = entry.unique_id.partition("_")[0]

        # Some devices, mainly routers, allow to change the hostname of the connected devices.
        # This can lead to entities no longer aligned to the device UI
        if (
            entry_host
            and entry_host in device_hosts_names
            and entry_mac in device_hosts_macs
        ):
            _LOGGER.debug(
                "Skipping entity %s [mac=%s, host=%s]",
                entry_name,
                entry_mac,
                entry_host,
            )
            continue
        # Entity is removed so that at the next coordinator update
        # the correct one will be created
        _LOGGER.info("Removing entity: %s", entry_name)
        entity_reg.async_remove(entry.entity_id)
        entities_removed = True

    if entities_removed:
        _async_remove_empty_devices(hass, entity_reg, config_entry)


def _async_remove_empty_devices(
    hass: HomeAssistant, entity_reg: er.EntityRegistry, config_entry: ConfigEntry
) -> None:
    """Remove devices with no entities."""

    device_reg = dr.async_get(hass)
    device_list = dr.async_entries_for_config_entry(device_reg, config_entry.entry_id)
    for device_entry in device_list:
        if not er.async_entries_for_device(
            entity_reg,
            device_entry.id,
            include_disabled_entities=True,
        ):
            _LOGGER.info("Removing device: %s", device_entry.name)
            device_reg.async_remove_device(device_entry.id)
