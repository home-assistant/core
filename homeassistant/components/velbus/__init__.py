"""Support for Velbus devices."""

import asyncio
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
import logging
import os
import shutil
from typing import Any

from velbusaio.controller import Velbus
from velbusaio.exceptions import VelbusConnectionFailed
from velbusaio.helpers import get_property_key_map
from velbusaio.module import Module

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, PlatformNotReady
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.storage import STORAGE_DIR
from homeassistant.helpers.typing import ConfigType

from .bus_sync import async_sync_bus_state
from .const import CONF_VLP_FILE, DOMAIN
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

RECONNECT_SCAN_COOLDOWN = 30.0

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.COVER,
    Platform.EVENT,
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
    known_unique_ids: set[str] = field(default_factory=set)
    discoverers: list[Callable[[], None]] = field(default_factory=list)
    reconnect_scan_debouncer: Debouncer[Coroutine[Any, Any, None]] | None = None


async def velbus_scan_task(controller: Velbus) -> None:
    """Task to offload the long running scan."""
    try:
        await controller.start()
    except ConnectionError as ex:
        raise PlatformNotReady(
            translation_domain=DOMAIN,
            translation_key="connection_failed",
        ) from ex


def _register_bus_listeners(hass: HomeAssistant, entry: VelbusConfigEntry) -> None:
    """Attach module and scan listeners on the controller."""
    controller = entry.runtime_data.controller

    async def on_module_found(_module: Module) -> None:
        """Keep the registries in sync when a module finishes loading."""
        await async_sync_bus_state(hass, entry)

    async def on_scan_complete(found_addresses: set[int]) -> None:
        """Reconcile devices and entities after a full bus scan."""
        await async_sync_bus_state(hass, entry, found_addresses=found_addresses)

    async def reconnect_scan() -> None:
        """Run a debounced full scan after reconnect."""
        try:
            await controller.scan()
        except OSError:
            _LOGGER.warning("Velbus reconnect scan failed", exc_info=True)

    debouncer = Debouncer(
        hass,
        _LOGGER,
        cooldown=RECONNECT_SCAN_COOLDOWN,
        immediate=False,
        function=reconnect_scan,
    )
    entry.runtime_data.reconnect_scan_debouncer = debouncer
    entry.async_on_unload(debouncer.async_shutdown)

    async def on_connect() -> None:
        """Schedule a bus scan after the connection comes back."""
        debouncer.async_schedule_call()

    controller.add_module_found_callback(on_module_found)
    controller.add_scan_complete_callback(on_scan_complete)
    controller.add_connect_callback(on_connect)

    def remove_listeners() -> None:
        controller.remove_module_found_callback(on_module_found)
        controller.remove_scan_complete_callback(on_scan_complete)
        controller.remove_connect_callback(on_connect)

    entry.async_on_unload(remove_listeners)


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

    property_key_map = await hass.async_add_executor_job(get_property_key_map)
    for entry in er.async_entries_for_config_entry(ent_reg, entry_id):
        if not entry.original_name:
            continue
        property_key = property_key_map.get(entry.original_name)
        if property_key is None:
            continue
        # Derive the serial from the entity's own unique_id, not from the device
        # registry, which another integration could overwrite. The program select
        # historically used `{serial}-{channel}-program_select`; every other property
        # uses channel number 0 (`{serial}-0`). Regular channels are always >=1, so a
        # `-0` suffix and the `-program_select` suffix only ever belong to properties.
        if entry.unique_id.endswith("-program_select"):
            serial = entry.unique_id.removesuffix("-program_select").rsplit("-", 1)[0]
        elif entry.unique_id.endswith("-0"):
            serial = entry.unique_id.removesuffix("-0")
        else:
            continue

        expected_unique_id = f"{serial}-{property_key}"
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


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the actions for the Velbus component."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: VelbusConfigEntry) -> None:
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

    entry.runtime_data = VelbusData(
        controller=controller,
        scan_task=hass.async_create_task(velbus_scan_task(controller)),
    )
    _register_bus_listeners(hass, entry)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: VelbusConfigEntry) -> None:
    """Unload (close) the velbus connection."""
    try:
        await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
    finally:
        await entry.runtime_data.controller.stop()


async def async_remove_entry(hass: HomeAssistant, entry: VelbusConfigEntry) -> None:
    """Remove the velbus entry, so we also have to cleanup the cache dir."""
    await hass.async_add_executor_job(
        shutil.rmtree,
        hass.config.path(STORAGE_DIR, f"velbuscache-{entry.entry_id}"),
    )


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    config_entry: VelbusConfigEntry,
    device_entry: dr.AnyDeviceEntry,
) -> bool:
    """Allow removing a Velbus device and its sub-devices.

    Sub-devices are removed along with their parent. If the device is still
    on the bus, it may be recreated when the integration is reloaded or
    started again.
    """
    if device_entry.config_entry_id != config_entry.entry_id:
        return False
    dev_reg = dr.async_get(hass)
    for sub_device in dr.async_entries_for_config_entry(dev_reg, config_entry.entry_id):
        if sub_device.via_device_id == device_entry.id:
            dev_reg.async_remove_device(sub_device.id)
    return True


async def async_migrate_entry(
    hass: HomeAssistant, config_entry: VelbusConfigEntry
) -> None:
    """Migrate old entry."""
    _LOGGER.error(
        "Migrating from version %s.%s", config_entry.version, config_entry.minor_version
    )

    # This is the config entry migration for swapping the
    # usb unique id to the serial number
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
