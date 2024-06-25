"""Reolink integration for HomeAssistant."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import timedelta
import logging

from reolink_aio.api import RETRY_ATTEMPTS
from reolink_aio.exceptions import CredentialsInvalidError, ReolinkError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import format_mac
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
NUM_CRED_ERRORS = 3


@dataclass
class ReolinkData:
    """Data for the Reolink integration."""

    host: ReolinkHost
    device_coordinator: DataUpdateCoordinator[None]
    firmware_coordinator: DataUpdateCoordinator[None]


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
                host.credential_errors += 1
                if host.credential_errors >= NUM_CRED_ERRORS:
                    await host.stop()
                    raise ConfigEntryAuthFailed(err) from err
                raise UpdateFailed(str(err)) from err
            except ReolinkError as err:
                host.credential_errors = 0
                raise UpdateFailed(str(err)) from err

        host.credential_errors = 0

        async with asyncio.timeout(host.api.timeout * (RETRY_ATTEMPTS + 2)):
            await host.renew()

    async def async_check_firmware_update() -> None:
        """Check for firmware updates."""
        async with asyncio.timeout(host.api.timeout * (RETRY_ATTEMPTS + 2)):
            try:
                await host.api.check_new_firmware(host.firmware_ch_list)
            except ReolinkError as err:
                if starting:
                    _LOGGER.debug(
                        "Error checking Reolink firmware update at startup "
                        "from %s, possibly internet access is blocked",
                        host.api.nvr_name,
                    )
                    return

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

    # first migrate and then cleanup, otherwise entities lost
    migrate_entity_ids(hass, config_entry.entry_id, host)
    cleanup_disconnected_cams(hass, config_entry.entry_id, host)

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


def get_device_uid_and_ch(
    device: dr.DeviceEntry, host: ReolinkHost
) -> tuple[list[str], int | None]:
    """Get the channel and the split device_uid from a reolink DeviceEntry."""
    device_uid = [
        dev_id[1].split("_") for dev_id in device.identifiers if dev_id[0] == DOMAIN
    ][0]

    if len(device_uid) < 2:
        # NVR itself
        ch = None
    elif device_uid[1].startswith("ch") and len(device_uid[1]) <= 5:
        ch = int(device_uid[1][2:])
    else:
        ch = host.api.channel_for_uid(device_uid[1])
    return (device_uid, ch)


def cleanup_disconnected_cams(
    hass: HomeAssistant, config_entry_id: str, host: ReolinkHost
) -> None:
    """Clean-up disconnected camera channels."""
    if not host.api.is_nvr:
        return

    device_reg = dr.async_get(hass)
    devices = dr.async_entries_for_config_entry(device_reg, config_entry_id)
    for device in devices:
        (device_uid, ch) = get_device_uid_and_ch(device, host)
        if ch is None:
            continue  # Do not consider the NVR itself

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


def migrate_entity_ids(
    hass: HomeAssistant, config_entry_id: str, host: ReolinkHost
) -> None:
    """Migrate entity IDs if needed."""
    device_reg = dr.async_get(hass)
    devices = dr.async_entries_for_config_entry(device_reg, config_entry_id)
    ch_device_ids = {}
    for device in devices:
        (device_uid, ch) = get_device_uid_and_ch(device, host)

        if host.api.supported(None, "UID") and device_uid[0] != host.unique_id:
            if ch is None:
                new_device_id = f"{host.unique_id}"
            else:
                new_device_id = f"{host.unique_id}_{device_uid[1]}"
            new_identifiers = {(DOMAIN, new_device_id)}
            device_reg.async_update_device(device.id, new_identifiers=new_identifiers)

        if ch is None:
            continue  # Do not consider the NVR itself

        ch_device_ids[device.id] = ch
        if host.api.supported(ch, "UID") and device_uid[1] != host.api.camera_uid(ch):
            if host.api.supported(None, "UID"):
                new_device_id = f"{host.unique_id}_{host.api.camera_uid(ch)}"
            else:
                new_device_id = f"{device_uid[0]}_{host.api.camera_uid(ch)}"
            new_identifiers = {(DOMAIN, new_device_id)}
            device_reg.async_update_device(device.id, new_identifiers=new_identifiers)

    entity_reg = er.async_get(hass)
    entities = er.async_entries_for_config_entry(entity_reg, config_entry_id)
    for entity in entities:
        # Can be removed in HA 2025.1.0
        if entity.domain == "update" and entity.unique_id in [
            host.unique_id,
            format_mac(host.api.mac_address),
        ]:
            entity_reg.async_update_entity(
                entity.entity_id, new_unique_id=f"{host.unique_id}_firmware"
            )
            continue

        if host.api.supported(None, "UID") and not entity.unique_id.startswith(
            host.unique_id
        ):
            new_id = f"{host.unique_id}_{entity.unique_id.split("_", 1)[1]}"
            entity_reg.async_update_entity(entity.entity_id, new_unique_id=new_id)

        if entity.device_id in ch_device_ids:
            ch = ch_device_ids[entity.device_id]
            id_parts = entity.unique_id.split("_", 2)
            if host.api.supported(ch, "UID") and id_parts[1] != host.api.camera_uid(ch):
                new_id = f"{host.unique_id}_{host.api.camera_uid(ch)}_{id_parts[2]}"
                entity_reg.async_update_entity(entity.entity_id, new_unique_id=new_id)
