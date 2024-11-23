"""Support for Velbus devices."""

from __future__ import annotations

import logging
import os
import shutil

from velbusaio.controller import Velbus

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.storage import STORAGE_DIR

from .const import DOMAIN, SERVICE_SCAN
from .services import cleanup_services, setup_services

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


async def velbus_connect_task(
    controller: Velbus, hass: HomeAssistant, entry_id: str
) -> None:
    """Task to offload the long running connect."""
    try:
        await controller.connect()
    except ConnectionError as ex:
        raise PlatformNotReady(
            f"Connection error while connecting to Velbus {entry_id}: {ex}"
        ) from ex


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


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Establish connection with velbus."""
    hass.data.setdefault(DOMAIN, {})

    controller = Velbus(
        entry.data[CONF_PORT],
        cache_dir=hass.config.path(STORAGE_DIR, f"velbuscache-{entry.entry_id}"),
    )
    hass.data[DOMAIN][entry.entry_id] = {}
    hass.data[DOMAIN][entry.entry_id]["cntrl"] = controller
    hass.data[DOMAIN][entry.entry_id]["tsk"] = hass.async_create_task(
        velbus_connect_task(controller, hass, entry.entry_id)
    )

    _migrate_device_identifiers(hass, entry.entry_id)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    if not hass.services.has_service(DOMAIN, SERVICE_SCAN):
        setup_services(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload (close) the velbus connection."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    await hass.data[DOMAIN][entry.entry_id]["cntrl"].stop()
    hass.data[DOMAIN].pop(entry.entry_id)
    if not hass.data[DOMAIN]:
        hass.data.pop(DOMAIN)
        cleanup_services(hass)
    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove the velbus entry, so we also have to cleanup the cache dir."""
    await hass.async_add_executor_job(
        shutil.rmtree,
        hass.config.path(STORAGE_DIR, f"velbuscache-{entry.entry_id}"),
    )


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    _LOGGER.debug("Migrating from version %s", config_entry.version)
    cache_path = hass.config.path(STORAGE_DIR, f"velbuscache-{config_entry.entry_id}/")
    if config_entry.version == 1:
        # This is the config entry migration for adding the new program selection
        # clean the velbusCache
        if os.path.isdir(cache_path):
            await hass.async_add_executor_job(shutil.rmtree, cache_path)
        # set the new version
        hass.config_entries.async_update_entry(config_entry, version=2)

    _LOGGER.debug("Migration to version %s successful", config_entry.version)
    return True
