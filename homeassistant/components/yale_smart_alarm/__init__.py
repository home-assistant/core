"""The yale_smart_alarm component."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import json
import logging

import async_timeout
import voluptuous as vol
from yalesmartalarmclient.client import AuthenticationError, YaleSmartAlarmClient

from homeassistant import exceptions
from homeassistant.const import CONF_CODE, CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.exceptions import (
    ConfigEntryNotReady,
    HomeAssistantError,
    PlatformNotReady,
)
from homeassistant.helpers import device_registry as dr, discovery
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import Throttle

from .const import CONF_AREA_ID, DEFAULT_AREA_ID, DEFAULT_NAME, DOMAIN, LOGGER
from .coordinator import YaleDataUpdateCoordinator


async def async_setup(hass, config):
    """ No setup from yaml for Yale """
    return True


async def async_setup_entry(hass, entry):
    """ Setup from config entries """
    hass.data.setdefault(DOMAIN, {})
    title = entry.title

    coordinator = YaleDataUpdateCoordinator(hass, entry=entry)

    await coordinator.async_refresh()
    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "data_listener": [entry.add_update_listener(update_listener)],
    }

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "alarm_control_panel")
    )

    hass.async_create_task(hass.config_entries.async_forward_entry_setup(entry, "lock"))

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "binary_sensor")
    )

    LOGGER.debug("Loaded entry for %s", title)

    return True


async def update_listener(hass, entry):
    """Update when config_entry options update."""
    entry = hass.data[DOMAIN][entry.entry_id]
    entry[CONF_CODE] = entry.options.get(CONF_CODE)
    LOGGER.debug("Code has been updated")


async def async_unload_entry(hass, entry):
    """Unload a config entry."""

    Platforms = []
    Platforms.append("alarm_control_panel")
    if hass.data[DOMAIN][entry.entry_id]["coordinator"].data["lock"] != []:
        Platforms.append("lock")
    if hass.data[DOMAIN][entry.entry_id]["coordinator"].data["door_window"] != []:
        Platforms.append("binary_sensor")

    for listener in hass.data[DOMAIN][entry.entry_id]["listener"]["data_listener"]:
        listener()

    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in Platforms
            ]
        )
    )

    title = entry.title
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        LOGGER.debug("Unloaded entry for %s", title)
        return unload_ok

    return False
