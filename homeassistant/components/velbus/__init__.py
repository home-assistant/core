"""Support for Velbus devices."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
import os
import shutil

from velbusaio.controller import Velbus
from velbusaio.exceptions import VelbusConnectionFailed
from velbusaio.helpers import get_property_key_map

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, PlatformNotReady
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.helpers.storage import STORAGE_DIR
from homeassistant.helpers.typing import ConfigType

from .const import CONF_VLP_FILE, DOMAIN
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.COVER,
    Platform.LIGHT,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type VelbusConfigEntry = ConfigEntry[VelbusData]


@dataclass
class VelbusData:
    """Runtime data for the Velbus config entry."""

    controller: Velbus
    scan_task: asyncio.Task


def _update_devices_and_issues(
    hass: HomeAssistant, controller: Velbus, entry_id: str
) -> None:
    """Sync device registry and stale-device repair issues with the current bus state."""
    dev_reg = dr.async_get(hass)
    found_addresses: set[str] = set()
    for module_address, module in controller.get_modules().items():
        address = str(module_address)
        found_addresses.add(address)
        dev_reg.async_get_or_create(
            config_entry_id=entry_id,
            identifiers={
                (DOMAIN, address),
            },
            manufacturer="Velleman",
            model=module.get_type_name(),
            model_id=str(module.get_type()),
            name=f"{module.get_name()} ({module.get_type_name()})",
            sw_version=module.get_sw_version(),
            serial_number=module.get_serial(),
        )
        ir.async_delete_issue(hass, DOMAIN, f"stale_device_{entry_id}_{address}")

    registered_addresses: set[str] = set()
    for device in dr.async_entries_for_config_entry(dev_reg, entry_id):
        device_address: str | None = next(
            (ident[1] for ident in device.identifiers if ident[0] == DOMAIN),
            None,
        )
        if device_address is None or device.via_device_id is not None:
            continue
        registered_addresses.add(device_address)
        if device_address in found_addresses:
            continue
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"stale_device_{entry_id}_{device_address}",
            is_fixable=False,
            is_persistent=True,
            severity=ir.IssueSeverity.WARNING,
            translation_key="stale_device",
            translation_placeholders={
                "name": device.name_by_user or device.name or device_address,
                "address": device_address,
            },
        )

    issue_prefix = f"stale_device_{entry_id}_"
    issue_reg = ir.async_get(hass)
    for domain, issue_id in list(issue_reg.issues):
        if domain == DOMAIN and issue_id.startswith(issue_prefix):
            address = issue_id[len(issue_prefix) :]
            if address not in registered_addresses:
                ir.async_delete_issue(hass, DOMAIN, issue_id)


async def velbus_scan_task(
    controller: Velbus, hass: HomeAssistant, entry_id: str
) -> None:
    """Task to offload the long running scan."""
    try:
        await controller.start()
    except ConnectionError as ex:
        raise PlatformNotReady(
            f"Connection error while connecting to Velbus {entry_id}: {ex}"
        ) from ex
    _update_devices_and_issues(hass, controller, entry_id)


def _migrate_device_identifiers(hass: HomeAssistant, entry_id: str) -> None:
    """Migrate old device identifiers."""
    dev_reg = dr.async_get(hass)
    devices: list[dr.DeviceEntry] = dr.async_entries_for_config_entry(dev_reg, entry_id)
    for device in devices:
        old_identifier = list(next(iter(device.identifiers)))
        if len(old_identifier) > 2:
            new_identifier = {(old_identifier.pop(0), old_identifier.pop(0))}
            _LOGGER.debug(
                "migrate identifier '%s' to '%s'", device.identifiers, new_identifier
            )
            dev_reg.async_update_device(device.id, new_identifiers=new_identifier)


async def _migrate_property_unique_ids(hass: HomeAssistant, entry_id: str) -> None:
    """Ensure property entity unique_ids use {serial}-{property_key} format."""
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)

    property_key_map = await hass.async_add_executor_job(get_property_key_map)
    for entry in er.async_entries_for_config_entry(ent_reg, entry_id):
        if not entry.original_name or not entry.device_id:
            continue
        property_key = property_key_map.get(entry.original_name)
        if property_key is None:
            continue
        device = dev_reg.async_get(entry.device_id)
        if device is None or device.via_device_id is not None:
            continue
        serial = device.serial_number or next(
            (ident[1] for ident in device.identifiers if ident[0] == DOMAIN), None
        )
        if serial is None:
            _LOGGER.debug(
                "Skipping unique_id migration for entity %s: device %s has no serial number or Velbus identifier",
                entry.entity_id,
                device.id,
            )
            continue

        expected_unique_id = f"{serial}-{property_key}"
        if entry.unique_id != expected_unique_id:
            if ent_reg.async_get_entity_id(entry.domain, DOMAIN, expected_unique_id):
                # Target unique_id already exists (created by new code) — remove stale entry
                _LOGGER.debug(
                    "Removing stale entity %s with outdated unique_id %s",
                    entry.entity_id,
                    entry.unique_id,
                )
                ent_reg.async_remove(entry.entity_id)
            else:
                _LOGGER.debug(
                    "Migrating unique_id %s → %s", entry.unique_id, expected_unique_id
                )
                ent_reg.async_update_entity(
                    entry.entity_id, new_unique_id=expected_unique_id
                )
        else:
            _LOGGER.debug(
                "Unique_id is ok: %s = %s", entry.unique_id, expected_unique_id
            )


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the actions for the Velbus component."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: VelbusConfigEntry) -> bool:
    """Establish connection with velbus."""
    controller = Velbus(
        dsn=entry.data[CONF_PORT],
        cache_dir=hass.config.path(STORAGE_DIR, f"velbuscache-{entry.entry_id}"),
        vlp_file=entry.data.get(CONF_VLP_FILE),
    )
    try:
        await controller.connect()
    except VelbusConnectionFailed as error:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="connection_failed",
        ) from error

    _migrate_device_identifiers(hass, entry.entry_id)
    # Migrate unique ids before the bus scan to preserve entity history
    await _migrate_property_unique_ids(hass, entry.entry_id)

    task = hass.async_create_task(velbus_scan_task(controller, hass, entry.entry_id))
    entry.runtime_data = VelbusData(controller=controller, scan_task=task)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: VelbusConfigEntry) -> bool:
    """Unload (close) the velbus connection."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    await entry.runtime_data.controller.stop()
    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: VelbusConfigEntry) -> None:
    """Remove the velbus entry, so we also have to cleanup the cache dir."""
    await hass.async_add_executor_job(
        shutil.rmtree,
        hass.config.path(STORAGE_DIR, f"velbuscache-{entry.entry_id}"),
    )


async def async_migrate_entry(
    hass: HomeAssistant, config_entry: VelbusConfigEntry
) -> bool:
    """Migrate old entry."""
    _LOGGER.error(
        "Migrating from version %s.%s", config_entry.version, config_entry.minor_version
    )

    # This is the config entry migration for swapping the usb unique id to the serial number
    # migrate from 2.1 to 2.2
    if (
        config_entry.version < 3
        and config_entry.minor_version == 1
        and config_entry.unique_id is not None
    ):
        # not all velbus devices have a unique id, so handle this correctly
        parts = config_entry.unique_id.split("_")
        # old one should have 4 item
        if len(parts) == 4:
            hass.config_entries.async_update_entry(config_entry, unique_id=parts[1])

    # This is the config entry migration for adding the new program selection
    # migrate from < 2 to 2.1
    # This is the config entry migration for adding the new properties
    # migrate from < 3 to 3.2
    if config_entry.version < 3:
        # clean the velbusCache
        cache_path = hass.config.path(
            STORAGE_DIR, f"velbuscache-{config_entry.entry_id}/"
        )
        if os.path.isdir(cache_path):
            await hass.async_add_executor_job(shutil.rmtree, cache_path)

    # update the config entry
    hass.config_entries.async_update_entry(config_entry, version=3, minor_version=2)

    _LOGGER.error(
        "Migration to version %s.%s successful",
        config_entry.version,
        config_entry.minor_version,
    )
    return True
