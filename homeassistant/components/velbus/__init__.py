"""Support for Velbus devices."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
import os
import shutil

from velbusaio.controller import Velbus
from velbusaio.exceptions import VelbusConnectionFailed

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, PlatformNotReady
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.storage import STORAGE_DIR
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .services import setup_services

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
    # create all modules
    dev_reg = dr.async_get(hass)
    for module in controller.get_modules().values():
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


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the actions for the Velbus component."""
    setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: VelbusConfigEntry) -> bool:
    """Establish connection with velbus."""
    controller = Velbus(
        entry.data[CONF_PORT],
        cache_dir=hass.config.path(STORAGE_DIR, f"velbuscache-{entry.entry_id}"),
    )
    try:
        await controller.connect()
    except VelbusConnectionFailed as error:
        raise ConfigEntryNotReady("Cannot connect to Velbus") from error

    task = hass.async_create_task(velbus_scan_task(controller, hass, entry.entry_id))
    entry.runtime_data = VelbusData(controller=controller, scan_task=task)

    _migrate_device_identifiers(hass, entry.entry_id)

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

    # This is the config entry migration for adding the new program selection
    # migrate from 1.x to 2.1
    if config_entry.version < 2:
        # clean the velbusCache
        cache_path = hass.config.path(
            STORAGE_DIR, f"velbuscache-{config_entry.entry_id}/"
        )
        if os.path.isdir(cache_path):
            await hass.async_add_executor_job(shutil.rmtree, cache_path)

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

    # update the config entry
    hass.config_entries.async_update_entry(config_entry, version=2, minor_version=2)

    _LOGGER.error(
        "Migration to version %s.%s successful",
        config_entry.version,
        config_entry.minor_version,
    )
    return True
