"""Reolink integration for HomeAssistant."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import timedelta
import logging

from aiohttp import ClientConnectorError
import async_timeout
from reolink_ip.exceptions import ApiError, InvalidContentTypeError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DEVICE_UPDATE_INTERVAL, DOMAIN, PLATFORMS
from .host import ReolinkHost

_LOGGER = logging.getLogger(__name__)


@dataclass
class ReolinkData:
    """Data for the Reolink integration."""

    host: ReolinkHost
    device_coordinator: DataUpdateCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Reolink from a config entry."""
    host = ReolinkHost(hass, dict(entry.data), dict(entry.options))

    try:
        if not await host.async_init():
            raise ConfigEntryNotReady(
                f"Error while trying to setup {host.api.host}:{host.api.port}: failed to obtain data from device."
            )
    except (
        ClientConnectorError,
        asyncio.TimeoutError,
        ApiError,
        InvalidContentTypeError,
    ) as err:
        raise ConfigEntryNotReady(
            f'Error while trying to setup {host.api.host}:{host.api.port}: "{str(err)}".'
        ) from err

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, host.stop)
    )

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

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = ReolinkData(
        host=host,
        device_coordinator=coordinator_device_config_update,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(entry_update_listener))

    return True


async def entry_update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Update the configuration of the host entity."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    host: ReolinkHost = hass.data[DOMAIN][entry.entry_id].host

    await host.stop()

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
