"""Reolink integration for HomeAssistant."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import Any

from reolink_aio.api import RETRY_ATTEMPTS
from reolink_aio.exceptions import (
    CredentialsInvalidError,
    LoginPrivacyModeError,
    ReolinkError,
)

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PORT, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_BC_PORT, CONF_SUPPORTS_PRIVACY_MODE, CONF_USE_HTTPS, DOMAIN
from .exceptions import PasswordIncompatible, ReolinkException, UserNotAdmin
from .host import ReolinkHost
from .services import async_setup_services
from .util import ReolinkConfigEntry, ReolinkData, get_device_uid_and_ch, get_store
from .views import PlaybackProxyView

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

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Reolink shared code."""

    async_setup_services(hass)
    return True


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ReolinkConfigEntry
) -> bool:
    """Set up Reolink from a config entry."""
    host = ReolinkHost(hass, config_entry.data, config_entry.options, config_entry)

    try:
        await host.async_init()
    except (UserNotAdmin, CredentialsInvalidError, PasswordIncompatible) as err:
        await host.stop()
        raise ConfigEntryAuthFailed(err) from err
    except (
        ReolinkException,
        ReolinkError,
    ) as err:
        await host.stop()
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="config_entry_not_ready",
            translation_placeholders={"host": host.api.host, "err": str(err)},
        ) from err
    except BaseException:
        await host.stop()
        raise

    config_entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, host.stop)
    )

    # update the config info if needed for the next time
    if (
        host.api.port != config_entry.data[CONF_PORT]
        or host.api.use_https != config_entry.data[CONF_USE_HTTPS]
        or host.api.supported(None, "privacy_mode")
        != config_entry.data.get(CONF_SUPPORTS_PRIVACY_MODE)
        or host.api.baichuan.port != config_entry.data.get(CONF_BC_PORT)
    ):
        if host.api.port != config_entry.data[CONF_PORT]:
            _LOGGER.warning(
                "HTTP(s) port of Reolink %s, changed from %s to %s",
                host.api.nvr_name,
                config_entry.data[CONF_PORT],
                host.api.port,
            )
        if (
            config_entry.data.get(CONF_BC_PORT, host.api.baichuan.port)
            != host.api.baichuan.port
        ):
            _LOGGER.warning(
                "Baichuan port of Reolink %s, changed from %s to %s",
                host.api.nvr_name,
                config_entry.data.get(CONF_BC_PORT),
                host.api.baichuan.port,
            )
        data = {
            **config_entry.data,
            CONF_PORT: host.api.port,
            CONF_USE_HTTPS: host.api.use_https,
            CONF_BC_PORT: host.api.baichuan.port,
            CONF_SUPPORTS_PRIVACY_MODE: host.api.supported(None, "privacy_mode"),
        }
        hass.config_entries.async_update_entry(config_entry, data=data)

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
            except LoginPrivacyModeError:
                pass  # HTTP API is shutdown when privacy mode is active
            except ReolinkError as err:
                host.credential_errors = 0
                raise UpdateFailed(str(err)) from err

        host.credential_errors = 0

        async with asyncio.timeout(host.api.timeout * (RETRY_ATTEMPTS + 2)):
            await host.renew()

        if host.api.new_devices and config_entry.state == ConfigEntryState.LOADED:
            # Their are new cameras/chimes connected, reload to add them.
            hass.async_create_task(
                hass.config_entries.async_reload(config_entry.entry_id)
            )

    async def async_check_firmware_update() -> None:
        """Check for firmware updates."""
        async with asyncio.timeout(host.api.timeout * (RETRY_ATTEMPTS + 2)):
            try:
                await host.api.check_new_firmware(host.firmware_ch_list)
            except ReolinkError as err:
                if host.starting:
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
            finally:
                host.starting = False

    device_coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        config_entry=config_entry,
        name=f"reolink.{host.api.nvr_name}",
        update_method=async_device_config_update,
        update_interval=DEVICE_UPDATE_INTERVAL,
    )
    firmware_coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        config_entry=config_entry,
        name=f"reolink.{host.api.nvr_name}.firmware",
        update_method=async_check_firmware_update,
        update_interval=FIRMWARE_UPDATE_INTERVAL,
    )

    # If camera WAN blocked, firmware check fails and takes long, do not prevent setup
    config_entry.async_create_background_task(
        hass,
        firmware_coordinator.async_refresh(),
        f"Reolink firmware check {config_entry.entry_id}",
    )
    # Fetch initial data so we have data when entities subscribe
    try:
        await device_coordinator.async_config_entry_first_refresh()
    except BaseException:
        await host.stop()
        raise

    config_entry.runtime_data = ReolinkData(
        host=host,
        device_coordinator=device_coordinator,
        firmware_coordinator=firmware_coordinator,
    )

    migrate_entity_ids(hass, config_entry.entry_id, host)

    hass.http.register_view(PlaybackProxyView(hass))

    async def refresh(*args: Any) -> None:
        """Request refresh of coordinator."""
        await device_coordinator.async_request_refresh()
        host.cancel_refresh_privacy_mode = None

    def async_privacy_mode_change() -> None:
        """Request update when privacy mode is turned off."""
        if host.privacy_mode and not host.api.baichuan.privacy_mode():
            # The privacy mode just turned off, give the API 2 seconds to start
            if host.cancel_refresh_privacy_mode is None:
                host.cancel_refresh_privacy_mode = async_call_later(hass, 2, refresh)
        host.privacy_mode = host.api.baichuan.privacy_mode()

    host.api.baichuan.register_callback(
        "privacy_mode_change", async_privacy_mode_change, 623
    )

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    config_entry.async_on_unload(
        config_entry.add_update_listener(entry_update_listener)
    )

    return True


async def entry_update_listener(
    hass: HomeAssistant, config_entry: ReolinkConfigEntry
) -> None:
    """Update the configuration of the host entity."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_unload_entry(
    hass: HomeAssistant, config_entry: ReolinkConfigEntry
) -> bool:
    """Unload a config entry."""
    host: ReolinkHost = config_entry.runtime_data.host

    await host.stop()

    host.api.baichuan.unregister_callback("privacy_mode_change")
    if host.cancel_refresh_privacy_mode is not None:
        host.cancel_refresh_privacy_mode()

    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)


async def async_remove_entry(
    hass: HomeAssistant, config_entry: ReolinkConfigEntry
) -> None:
    """Handle removal of an entry."""
    store = get_store(hass, config_entry.entry_id)
    await store.async_remove()


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ReolinkConfigEntry, device: dr.DeviceEntry
) -> bool:
    """Remove a device from a config entry."""
    host: ReolinkHost = config_entry.runtime_data.host
    (device_uid, ch, is_chime) = get_device_uid_and_ch(device, host)

    if is_chime:
        await host.api.get_state(cmd="GetDingDongList")
        chime = host.api.chime(ch)
        if (
            chime is None
            or chime.connect_state is None
            or chime.connect_state < 0
            or chime.channel not in host.api.channels
        ):
            _LOGGER.debug(
                "Removing Reolink chime %s with id %s, "
                "since it is not coupled to %s anymore",
                device.name,
                ch,
                host.api.nvr_name,
            )
            return True

        # remove the chime from the host
        await chime.remove()
        await host.api.get_state(cmd="GetDingDongList")
        if chime.connect_state < 0:
            _LOGGER.debug(
                "Removed Reolink chime %s with id %s from %s",
                device.name,
                ch,
                host.api.nvr_name,
            )
            return True

        _LOGGER.warning(
            "Cannot remove Reolink chime %s with id %s, because it is still connected "
            "to %s, please first remove the chime "
            "in the reolink app",
            device.name,
            ch,
            host.api.nvr_name,
        )
        return False

    if not host.api.is_nvr or ch is None:
        _LOGGER.warning(
            "Cannot remove Reolink device %s, because it is not a camera connected "
            "to a NVR/Hub, please remove the integration entry instead",
            device.name,
        )
        return False  # Do not remove the host/NVR itself

    if ch not in host.api.channels:
        _LOGGER.debug(
            "Removing Reolink device %s, "
            "since no camera is connected to NVR channel %s anymore",
            device.name,
            ch,
        )
        return True

    await host.api.get_state(cmd="GetChannelstatus")  # update the camera_online status
    if not host.api.camera_online(ch):
        _LOGGER.debug(
            "Removing Reolink device %s, "
            "since the camera connected to channel %s is offline",
            device.name,
            ch,
        )
        return True

    _LOGGER.warning(
        "Cannot remove Reolink device %s on channel %s, because it is still connected "
        "to the NVR/Hub, please first remove the camera from the NVR/Hub "
        "in the reolink app",
        device.name,
        ch,
    )
    return False


def migrate_entity_ids(
    hass: HomeAssistant, config_entry_id: str, host: ReolinkHost
) -> None:
    """Migrate entity IDs if needed."""
    device_reg = dr.async_get(hass)
    devices = dr.async_entries_for_config_entry(device_reg, config_entry_id)
    ch_device_ids = {}
    for device in devices:
        (device_uid, ch, is_chime) = get_device_uid_and_ch(device, host)

        if host.api.supported(None, "UID") and device_uid[0] != host.unique_id:
            if ch is None:
                new_device_id = f"{host.unique_id}"
            else:
                new_device_id = f"{host.unique_id}_{device_uid[1]}"
            new_identifiers = {(DOMAIN, new_device_id)}
            device_reg.async_update_device(device.id, new_identifiers=new_identifiers)

        if ch is None or is_chime:
            continue  # Do not consider the NVR itself or chimes

        ch_device_ids[device.id] = ch
        if host.api.supported(ch, "UID") and device_uid[1] != host.api.camera_uid(ch):
            if host.api.supported(None, "UID"):
                new_device_id = f"{host.unique_id}_{host.api.camera_uid(ch)}"
            else:
                new_device_id = f"{device_uid[0]}_{host.api.camera_uid(ch)}"
            new_identifiers = {(DOMAIN, new_device_id)}
            existing_device = device_reg.async_get_device(identifiers=new_identifiers)
            if existing_device is None:
                device_reg.async_update_device(
                    device.id, new_identifiers=new_identifiers
                )
            else:
                _LOGGER.warning(
                    "Reolink device with uid %s already exists, "
                    "removing device with uid %s",
                    new_device_id,
                    device_uid,
                )
                device_reg.async_remove_device(device.id)

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
            new_id = f"{host.unique_id}_{entity.unique_id.split('_', 1)[1]}"
            entity_reg.async_update_entity(entity.entity_id, new_unique_id=new_id)

        if entity.device_id in ch_device_ids:
            ch = ch_device_ids[entity.device_id]
            id_parts = entity.unique_id.split("_", 2)
            if host.api.supported(ch, "UID") and id_parts[1] != host.api.camera_uid(ch):
                new_id = f"{host.unique_id}_{host.api.camera_uid(ch)}_{id_parts[2]}"
                existing_entity = entity_reg.async_get_entity_id(
                    entity.domain, entity.platform, new_id
                )
                if existing_entity is None:
                    entity_reg.async_update_entity(
                        entity.entity_id, new_unique_id=new_id
                    )
                else:
                    _LOGGER.warning(
                        "Reolink entity with unique_id %s already exists, "
                        "removing device with unique_id %s",
                        new_id,
                        entity.unique_id,
                    )
                    entity_reg.async_remove(entity.entity_id)
