"""Reolink integration for HomeAssistant."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Literal

from reolink_aio.api import RETRY_ATTEMPTS
from reolink_aio.exceptions import CredentialsInvalidError, ReolinkError
from reolink_aio.software_version import NewSoftwareVersion

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .exceptions import ReolinkException, UserNotAdmin
from .host import ReolinkHost

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CAMERA,
    Platform.LIGHT,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SIREN,
    Platform.SWITCH,
    Platform.UPDATE,
]
DEVICE_UPDATE_INTERVAL = timedelta(seconds=60)
FIRMWARE_UPDATE_INTERVAL = timedelta(hours=12)


@dataclass
class ReolinkData:
    """Data for the Reolink integration."""

    host: ReolinkHost
    device_coordinator: DataUpdateCoordinator[None]
    firmware_coordinator: DataUpdateCoordinator[
        str | Literal[False] | NewSoftwareVersion
    ]


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up Reolink from a config entry."""
    host = ReolinkHost(hass, config_entry.data, config_entry.options)

    try:
        await host.async_init()
    except (UserNotAdmin, CredentialsInvalidError) as err:
        await host.stop()
        raise ConfigEntryAuthFailed(err) from err
    except (
        ReolinkException,
        ReolinkError,
    ) as err:
        await host.stop()
        raise ConfigEntryNotReady(
            f"Error while trying to setup {host.api.host}:{host.api.port}: {err!s}"
        ) from err
    except Exception:
        await host.stop()
        raise

    config_entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, host.stop)
    )

    starting = True

    async def async_device_config_update() -> None:
        """Update the host state cache and renew the ONVIF-subscription."""
        async with asyncio.timeout(host.api.timeout * (RETRY_ATTEMPTS + 2)):
            try:
                await host.update_states()
            except CredentialsInvalidError as err:
                await host.stop()
                raise ConfigEntryAuthFailed(err) from err
            except ReolinkError as err:
                raise UpdateFailed(str(err)) from err

        async with asyncio.timeout(host.api.timeout * (RETRY_ATTEMPTS + 2)):
            await host.renew()

    async def async_check_firmware_update() -> (
        str | Literal[False] | NewSoftwareVersion
    ):
        """Check for firmware updates."""
        if not host.api.supported(None, "update"):
            return False

        async with asyncio.timeout(host.api.timeout * (RETRY_ATTEMPTS + 2)):
            try:
                return await host.api.check_new_firmware()
            except ReolinkError as err:
                if starting:
                    _LOGGER.debug(
                        "Error checking Reolink firmware update at startup "
                        "from %s, possibly internet access is blocked",
                        host.api.nvr_name,
                    )
                    return False

                raise UpdateFailed(
                    f"Error checking Reolink firmware update from {host.api.nvr_name}, "
                    "if the camera is blocked from accessing the internet, "
                    "disable the update entity"
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
    results = await asyncio.gather(
        device_coordinator.async_config_entry_first_refresh(),
        firmware_coordinator.async_config_entry_first_refresh(),
        return_exceptions=True,
    )
    # If camera WAN blocked, firmware check fails, do not prevent setup
    # so don't check firmware_coordinator exceptions
    if isinstance(results[0], BaseException):
        await host.stop()
        raise results[0]

    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = ReolinkData(
        host=host,
        device_coordinator=device_coordinator,
        firmware_coordinator=firmware_coordinator,
    )

    cleanup_disconnected_cams(hass, config_entry.entry_id, host)

    # Can be remove in HA 2024.6.0
    entity_reg = er.async_get(hass)
    entities = er.async_entries_for_config_entry(entity_reg, config_entry.entry_id)
    for entity in entities:
        if entity.domain == "light" and entity.unique_id.endswith("ir_lights"):
            entity_reg.async_remove(entity.entity_id)

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    config_entry.async_on_unload(
        config_entry.add_update_listener(entry_update_listener)
    )

    starting = False
    return True


async def entry_update_listener(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
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


def cleanup_disconnected_cams(
    hass: HomeAssistant, config_entry_id: str, host: ReolinkHost
) -> None:
    """Clean-up disconnected camera channels."""
    if not host.api.is_nvr:
        return

    device_reg = dr.async_get(hass)
    devices = dr.async_entries_for_config_entry(device_reg, config_entry_id)
    for device in devices:
        device_id = [
            dev_id[1].split("_ch")
            for dev_id in device.identifiers
            if dev_id[0] == DOMAIN
        ][0]

        if len(device_id) < 2:
            # Do not consider the NVR itself
            continue

        ch = int(device_id[1])
        ch_model = host.api.camera_model(ch)
        remove = False
        if ch not in host.api.channels:
            remove = True
            _LOGGER.debug(
                "Removing Reolink device %s, "
                "since no camera is connected to NVR channel %s anymore",
                device.name,
                ch,
            )
        if ch_model not in [device.model, "Unknown"]:
            remove = True
            _LOGGER.debug(
                "Removing Reolink device %s, "
                "since the camera model connected to channel %s changed from %s to %s",
                device.name,
                ch,
                device.model,
                ch_model,
            )
        if not remove:
            continue

        # clean device registry and associated entities
        device_reg.async_remove_device(device.id)
