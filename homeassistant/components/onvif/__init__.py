"""The ONVIF integration."""

import asyncio
from contextlib import suppress
from http import HTTPStatus
import logging

from httpx import RequestError
from onvif.exceptions import ONVIFError
from onvif.util import is_auth_error, stringify_onvif_error
from zeep.exceptions import Fault, TransportError

from homeassistant.components.ffmpeg import CONF_EXTRA_ARGUMENTS
from homeassistant.components.stream import CONF_RTSP_TRANSPORT, RTSP_TRANSPORTS
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    EVENT_HOMEASSISTANT_STOP,
    HTTP_BASIC_AUTHENTICATION,
    HTTP_DIGEST_AUTHENTICATION,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er

from .const import (
    CONF_ENABLE_WEBHOOKS,
    CONF_SNAPSHOT_AUTH,
    DEFAULT_ARGUMENTS,
    DEFAULT_ENABLE_WEBHOOKS,
    DOMAIN,
)
from .device import ONVIFDevice

LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up ONVIF from a config entry."""
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    if not entry.options:
        await async_populate_options(hass, entry)

    device = ONVIFDevice(hass, entry)

    try:
        await device.async_setup()
        if not entry.data.get(CONF_SNAPSHOT_AUTH):
            await async_populate_snapshot_auth(hass, device, entry)
    except RequestError as err:
        await device.device.close()
        raise ConfigEntryNotReady(
            f"Could not connect to camera {device.device.host}:{device.device.port}: {err}"
        ) from err
    except Fault as err:
        await device.device.close()
        if is_auth_error(err):
            raise ConfigEntryAuthFailed(
                f"Auth Failed: {stringify_onvif_error(err)}"
            ) from err
        raise ConfigEntryNotReady(
            f"Could not connect to camera: {stringify_onvif_error(err)}"
        ) from err
    except ONVIFError as err:
        await device.device.close()
        raise ConfigEntryNotReady(
            f"Could not setup camera {device.device.host}:{device.device.port}: {stringify_onvif_error(err)}"
        ) from err
    except TransportError as err:
        await device.device.close()
        stringified_onvif_error = stringify_onvif_error(err)
        if err.status_code in (
            HTTPStatus.UNAUTHORIZED.value,
            HTTPStatus.FORBIDDEN.value,
        ):
            raise ConfigEntryAuthFailed(
                f"Auth Failed: {stringified_onvif_error}"
            ) from err
        raise ConfigEntryNotReady(
            f"Could not setup camera {device.device.host}:{device.device.port}: {stringified_onvif_error}"
        ) from err
    except asyncio.CancelledError as err:
        # After https://github.com/agronholm/anyio/issues/374 is resolved
        # this may be able to be removed
        await device.device.close()
        raise ConfigEntryNotReady(f"Setup was unexpectedly canceled: {err}") from err

    if not device.available:
        raise ConfigEntryNotReady

    hass.data[DOMAIN][entry.unique_id] = device

    device.platforms = [Platform.BUTTON, Platform.CAMERA]

    if device.capabilities.events:
        device.platforms += [Platform.BINARY_SENSOR, Platform.SENSOR]

    if device.capabilities.imaging:
        device.platforms += [Platform.SWITCH]

    _async_migrate_camera_entities_unique_ids(hass, entry, device)

    await hass.config_entries.async_forward_entry_setups(entry, device.platforms)

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, device.async_stop)
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    device: ONVIFDevice = hass.data[DOMAIN][entry.unique_id]

    if device.capabilities.events and device.events.started:
        try:
            await device.events.async_stop()
        except (ONVIFError, Fault, RequestError, TransportError):
            LOGGER.warning("Error while stopping events: %s", device.name)

    return await hass.config_entries.async_unload_platforms(entry, device.platforms)


async def _get_snapshot_auth(device: ONVIFDevice) -> str | None:
    """Determine auth type for snapshots."""
    if not device.capabilities.snapshot:
        return None

    for basic_auth in (False, True):
        method = HTTP_BASIC_AUTHENTICATION if basic_auth else HTTP_DIGEST_AUTHENTICATION
        with suppress(ONVIFError):
            if await device.device.get_snapshot(device.profiles[0].token, basic_auth):
                return method

    return None


async def async_populate_snapshot_auth(
    hass: HomeAssistant, device: ONVIFDevice, entry: ConfigEntry
) -> None:
    """Check if digest auth for snapshots is possible."""
    if auth := await _get_snapshot_auth(device):
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_SNAPSHOT_AUTH: auth}
        )


async def async_populate_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Populate default options for device."""
    options = {
        CONF_EXTRA_ARGUMENTS: DEFAULT_ARGUMENTS,
        CONF_RTSP_TRANSPORT: next(iter(RTSP_TRANSPORTS)),
        CONF_ENABLE_WEBHOOKS: DEFAULT_ENABLE_WEBHOOKS,
    }

    hass.config_entries.async_update_entry(entry, options=options)


@callback
def _async_migrate_camera_entities_unique_ids(
    hass: HomeAssistant, config_entry: ConfigEntry, device: ONVIFDevice
) -> None:
    """Migrate unique ids of camera entities from profile index to profile token."""
    entity_reg = er.async_get(hass)
    entities: list[er.RegistryEntry] = er.async_entries_for_config_entry(
        entity_reg, config_entry.entry_id
    )

    mac_or_serial = device.info.mac or device.info.serial_number
    old_uid_start = f"{mac_or_serial}_"
    new_uid_start = f"{mac_or_serial}#"

    for entity in entities:
        if entity.domain != Platform.CAMERA:
            continue

        if (
            not entity.unique_id.startswith(old_uid_start)
            and entity.unique_id != mac_or_serial
        ):
            continue

        index = 0
        if entity.unique_id.startswith(old_uid_start):
            try:
                index = int(entity.unique_id[len(old_uid_start) :])
            except ValueError:
                LOGGER.error(
                    "Failed to migrate unique id for '%s' as the ONVIF profile index could not be parsed from unique id '%s'",
                    entity.entity_id,
                    entity.unique_id,
                )
                continue
        try:
            token = device.profiles[index].token
        except IndexError:
            LOGGER.error(
                "Failed to migrate unique id for '%s' as the ONVIF profile index '%d' parsed from unique id '%s' could not be found",
                entity.entity_id,
                index,
                entity.unique_id,
            )
            continue
        new_uid = f"{new_uid_start}{token}"
        LOGGER.debug(
            "Migrating unique id for '%s' from '%s' to '%s'",
            entity.entity_id,
            entity.unique_id,
            new_uid,
        )
        entity_reg.async_update_entity(entity.entity_id, new_unique_id=new_uid)
