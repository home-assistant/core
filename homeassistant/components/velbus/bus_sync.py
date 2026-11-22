"""Synchronise the Velbus device and entity registries with the live bus."""

import logging
from typing import TYPE_CHECKING

from velbusaio.module import Module

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import DOMAIN
from .entity_discovery import entity_registry_key

if TYPE_CHECKING:
    from . import VelbusConfigEntry

_LOGGER = logging.getLogger(__name__)


def _module_address_from_identifier(identifier: str) -> int | None:
    """Parse a module address from a Velbus device identifier."""
    address_part = identifier.split("-", 1)[0]
    try:
        return int(address_part)
    except ValueError:
        return None


def _upsert_module_device(
    dev_reg: dr.DeviceRegistry, entry_id: str, module: Module
) -> None:
    """Create or update the registry entry for a module."""
    dev_reg.async_get_or_create(
        config_entry_id=entry_id,
        identifiers={
            (DOMAIN, str(module.get_addresses()[0])),
        },
        manufacturer="Velleman",
        model=module.get_type_name(),
        model_id=str(module.get_type()),
        name=f"{module.get_name()} ({module.get_type_name()})",
        sw_version=module.get_sw_version(),
        serial_number=module.get_serial(),
    )


def _upsert_module_devices(
    hass: HomeAssistant,
    entry: VelbusConfigEntry,
    *,
    module_addresses: set[int] | None = None,
) -> None:
    """Ensure every loaded module has a device registry entry."""
    dev_reg = dr.async_get(hass)
    for module in entry.runtime_data.controller.get_modules().values():
        addresses = set(module.get_addresses())
        if module_addresses is not None and not addresses.intersection(
            module_addresses
        ):
            continue
        _upsert_module_device(dev_reg, entry.entry_id, module)


def _remove_stale_devices(
    hass: HomeAssistant, entry: VelbusConfigEntry, found_addresses: set[int]
) -> None:
    """Remove devices and entities for modules absent from a full bus scan."""
    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)
    data = entry.runtime_data

    stale_device_ids: list[str] = []
    for device in dr.async_entries_for_config_entry(dev_reg, entry.entry_id):
        for domain, identifier in device.identifiers:
            if domain != DOMAIN:
                continue
            module_address = _module_address_from_identifier(identifier)
            if module_address is None:
                continue
            if module_address not in found_addresses:
                stale_device_ids.append(device.id)
                break

    for device_id in stale_device_ids:
        removal_device_ids = {device_id}
        removal_device_ids.update(
            child.id for child in dr.async_entries_for_parent_device(dev_reg, device_id)
        )
        for entity in er.async_entries_for_config_entry(ent_reg, entry.entry_id):
            if entity.device_id not in removal_device_ids:
                continue
            if entity.unique_id:
                data.known_unique_ids.discard(
                    entity_registry_key(entity.domain, entity.unique_id)
                )
            ent_reg.async_remove(entity.entity_id)
        stale_device = dev_reg.async_get(device_id)
        if stale_device is not None:
            _LOGGER.debug(
                "Removing stale Velbus device %s after bus scan", stale_device.name
            )
            dev_reg.async_remove_device(device_id)


async def async_sync_bus_state(
    hass: HomeAssistant,
    entry: VelbusConfigEntry,
    *,
    found_addresses: set[int] | None = None,
    restrict_to_addresses: set[int] | None = None,
) -> None:
    """Update devices and entities from the controller's current bus state."""
    data = entry.runtime_data

    if found_addresses is not None:
        data.scanned_module_addresses = set(found_addresses)

    upsert_addresses: set[int] | None
    if restrict_to_addresses is not None:
        upsert_addresses = restrict_to_addresses
        if data.scanned_module_addresses is not None:
            data.scanned_module_addresses.update(restrict_to_addresses)
    elif data.scanned_module_addresses is not None:
        upsert_addresses = data.scanned_module_addresses
    else:
        upsert_addresses = None

    _upsert_module_devices(hass, entry, module_addresses=upsert_addresses)

    if found_addresses is not None:
        _remove_stale_devices(hass, entry, found_addresses)

    discovery_filter = restrict_to_addresses or data.scanned_module_addresses
    for discoverer in data.discoverers:
        discoverer(discovery_filter)
