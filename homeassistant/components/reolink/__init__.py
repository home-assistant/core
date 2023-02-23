"""Reolink integration for HomeAssistant."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import timedelta
import logging

from aiohttp import ClientConnectorError
import async_timeout
from reolink_aio.exceptions import CredentialsInvalidError, ReolinkError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .exceptions import ReolinkException, UserNotAdmin
from .host import ReolinkHost

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.BINARY_SENSOR, Platform.CAMERA, Platform.NUMBER, Platform.UPDATE]
DEVICE_UPDATE_INTERVAL = timedelta(seconds=60)
FIRMWARE_UPDATE_INTERVAL = timedelta(hours=12)


@dataclass
class ReolinkData:
    """Data for the Reolink integration."""

    host: ReolinkHost
    device_coordinator: DataUpdateCoordinator
    firmware_coordinator: DataUpdateCoordinator


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up Reolink from a config entry."""
    host = ReolinkHost(hass, config_entry.data, config_entry.options)

    try:
        await host.async_init()
    except (UserNotAdmin, CredentialsInvalidError) as err:
        await host.stop()
        raise ConfigEntryAuthFailed(err) from err
    except (
        ClientConnectorError,
        asyncio.TimeoutError,
        ReolinkException,
        ReolinkError,
    ) as err:
        await host.stop()
        raise ConfigEntryNotReady(
            f"Error while trying to setup {host.api.host}:{host.api.port}: {str(err)}"
        ) from err
    except Exception:  # pylint: disable=broad-except
        await host.stop()
        raise

    config_entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, host.stop)
    )

    async def async_device_config_update():
        """Update the host state cache and renew the ONVIF-subscription."""
        async with async_timeout.timeout(host.api.timeout):
            try:
                await host.update_states()
            except ReolinkError as err:
                raise UpdateFailed(
                    f"Error updating Reolink {host.api.nvr_name}"
                ) from err

        async with async_timeout.timeout(host.api.timeout):
            await host.renew()

    async def async_check_firmware_update():
        """Check for firmware updates."""
        if not host.api.supported(None, "update"):
            return False

        async with async_timeout.timeout(host.api.timeout):
            try:
                return await host.api.check_new_firmware()
            except ReolinkError as err:
                raise UpdateFailed(
                    f"Error checking Reolink firmware update {host.api.nvr_name}"
                ) from err

    device_coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"reolink.{host.api.nvr_name}",
        update_method=async_device_config_update,
        update_interval=DEVICE_UPDATE_INTERVAL,
    )
    firmware_coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"reolink.{host.api.nvr_name}.firmware",
        update_method=async_check_firmware_update,
        update_interval=FIRMWARE_UPDATE_INTERVAL,
    )
    # Fetch initial data so we have data when entities subscribe
    try:
        await asyncio.gather(
            device_coordinator.async_config_entry_first_refresh(),
            firmware_coordinator.async_config_entry_first_refresh(),
        )
    except ConfigEntryNotReady:
        await host.stop()
        raise

    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = ReolinkData(
        host=host,
        device_coordinator=device_coordinator,
        firmware_coordinator=firmware_coordinator,
    )

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    config_entry.async_on_unload(
        config_entry.add_update_listener(entry_update_listener)
    )

    return True


async def entry_update_listener(hass: HomeAssistant, config_entry: ConfigEntry):
    """Update the configuration of the host entity."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    host: ReolinkHost = hass.data[DOMAIN][config_entry.entry_id].host

    await host.stop()

    if unload_ok := await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    ):
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok
