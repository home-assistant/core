"""Refoss devices platform loader"""
from __future__ import annotations

from typing import  Collection
from datetime import  timedelta
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MAC
from homeassistant.core import HomeAssistant
from refoss_ha.http_device import HttpDeviceInfo
from refoss_ha.const import (
    DOMAIN,
    LOGGER,
    DEVICE_LIST_COORDINATOR,
    SOCKET_DISCOVER_UPDATE_INTERVAL,
    MEROSS_PLATFORMS
)
from .coordinator import MerossCoordinator



async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    if not config_entry.data.get(CONF_MAC):
        LOGGER.warning(
            (
                "The config entry %s probably comes from a custom integration, please"
                " remove it if you want to use core meross integration"
            ),
            config_entry.title,
        )
        return False
    hass.data[DOMAIN] = {}
    meross_coordinator = MerossCoordinator(hass=hass, config_entry=config_entry,

                                           update_interval=timedelta(seconds=SOCKET_DISCOVER_UPDATE_INTERVAL))
    try:
        await meross_coordinator.initial_setup()
    except Exception as e:
        LOGGER.warning("initial_setup failed: %s", e)
        return False

    hass.data[DOMAIN]["ADDED_ENTITIES_IDS"] = set()

    hass.data[DOMAIN][DEVICE_LIST_COORDINATOR] = meross_coordinator


    for platform in MEROSS_PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, platform)
        )

    def _poll_discovered_device(*args, **kwargs):
        discovered_devices = meross_coordinator.data

        known_devices = meross_coordinator.find_devices()


        if _check_new_discovered_device(known_devices, discovered_devices.values()):
            hass.create_task(meross_coordinator.async_device_discovery(
                                                         cached_http_device_list=discovered_devices.values()))


    meross_coordinator.async_add_listener(_poll_discovered_device)
    return True



def _check_new_discovered_device(known: Collection[HttpDeviceInfo], discovered: Collection[HttpDeviceInfo]) -> bool:
    known_ids = [dev.uuid for dev in known]
    unknown = [dev for dev in discovered if dev.uuid not in known_ids]
    return len(unknown) > 0

async def async_unload_entry(hass, entry):
    meross_coordinator:MerossCoordinator=hass.data[DOMAIN][DEVICE_LIST_COORDINATOR]
    for platform in MEROSS_PLATFORMS:
        await hass.config_entries.async_forward_entry_unload(entry, platform)

    meross_coordinator.merossSocket.stopReveiveMsg()
    del hass.data[DOMAIN][DEVICE_LIST_COORDINATOR]
    hass.data[DOMAIN].clear()
    return True

