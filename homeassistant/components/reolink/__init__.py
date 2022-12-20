"""Reolink integration for HomeAssistant."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import cast

import async_timeout

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    DEVICE_CONFIG_UPDATE_COORDINATOR,
    DEVICE_UPDATE_INTERVAL,
    DOMAIN,
    HOST,
    PLATFORMS,
    SERVICE_PTZ_CONTROL,
    SERVICE_SET_BACKLIGHT,
    SERVICE_SET_DAYNIGHT,
    SERVICE_SET_SENSITIVITY,
)
from .host import ReolinkHost

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Reolink from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    host = ReolinkHost(hass, dict(entry.data), dict(entry.options))

    try:
        if not await host.init():
            raise ConfigEntryNotReady(
                f"Error while trying to setup {host.api.host}:{host.api.port}: failed to obtain data from device."
            )
    except Exception as error:  # pylint: disable=broad-except
        err = str(error)
        if err:
            raise ConfigEntryNotReady(
                f'Error while trying to setup {host.api.host}:{host.api.port}: "{err}".'
            ) from error
        raise ConfigEntryNotReady(
            f"Error while trying to setup {host.api.host}:{host.api.port}: failed to connect to device."
        ) from error

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, host.stop)
    )

    hass.data[DOMAIN][entry.entry_id] = {HOST: host}

    async def async_device_config_update():
        """Perform the update of the host config-state cache, and renew the ONVIF-subscription."""
        async with async_timeout.timeout(host.api.timeout):
            await host.update_states()  # Login session is implicitly updated here, so no need to explicitly do it in a timer

    coordinator_device_config_update = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"reolink.{host.api.nvr_name}",
        update_method=async_device_config_update,
        update_interval=timedelta(seconds=DEVICE_UPDATE_INTERVAL),
    )
    # Fetch initial data so we have data when entities subscribe
    await coordinator_device_config_update.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id][
        DEVICE_CONFIG_UPDATE_COORDINATOR
    ] = coordinator_device_config_update

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(entry_update_listener))

    return True


async def entry_update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Update the configuration of the host entity."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    host: ReolinkHost = hass.data[DOMAIN][entry.entry_id][HOST]

    await host.stop()

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
        hass.data[DOMAIN].pop(entry.entry_id)

    if len(hass.data[DOMAIN]) == 0:
        hass.services.async_remove(DOMAIN, SERVICE_SET_SENSITIVITY)
        hass.services.async_remove(DOMAIN, SERVICE_SET_DAYNIGHT)
        hass.services.async_remove(DOMAIN, SERVICE_SET_BACKLIGHT)
        hass.services.async_remove(DOMAIN, SERVICE_PTZ_CONTROL)

    return unload_ok
