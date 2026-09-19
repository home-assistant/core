"""The Zentraly integration."""

import asyncio
from datetime import datetime
import logging

from zentraly import (
    ZentralyApi,
    ZentralyApiError,
    ZentralyAuthenticationError,
    ZentralyConnectionError,
    get_device_commands,
    get_device_model,
)

from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_HOST,
    CONF_MAC,
    CONF_PASSWORD,
    CONF_PORT,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import UNDEFINED

from .const import DEVICE_INFO_INTERVAL, DOMAIN
from .models import ZentralyConfigEntry, ZentralyData, ZentralyDevice
from .platforms import get_device_platforms

_LOGGER = logging.getLogger(__name__)


def create_device(
    api: ZentralyApi,
    device_id: str,
    mac: str,
) -> ZentralyDevice:
    """Create a runtime representation of a Zentraly device."""

    device_model = get_device_model(device_id)

    if not get_device_platforms(device_id):
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="unsupported_model",
            translation_placeholders={"device_id": device_id},
        )

    commands = get_device_commands(device_model)

    return ZentralyDevice(
        api=api,
        device_id=device_id,
        mac=mac,
        device_model=device_model,
        commands=commands,
    )


async def _async_refresh_device_info(
    device: ZentralyDevice,
    device_registry: dr.DeviceRegistry,
    registry_device_id: str,
) -> None:
    """Refresh firmware and hardware information for a Zentraly device."""

    if not device.connected:
        return

    try:
        info = await device.async_get_device_info()
    except ZentralyApiError:
        _LOGGER.debug(
            "Unable to refresh Zentraly device information for %s", device.device_id
        )
        return
    firmware_version = info.firmware_version
    hardware_version = info.hardware_version

    changed = False

    if firmware_version is not None and firmware_version != device.firmware_version:
        device.firmware_version = firmware_version
        changed = True

    if hardware_version is not None and hardware_version != device.hardware_version:
        device.hardware_version = hardware_version
        changed = True

    if not changed:
        return

    device_registry.async_update_device(
        registry_device_id,
        sw_version=firmware_version if firmware_version is not None else UNDEFINED,
        hw_version=hardware_version if hardware_version is not None else UNDEFINED,
    )

    _LOGGER.debug(
        "Updated Zentraly device information: device_id=%s firmware=%s hardware=%s",
        device.device_id,
        device.firmware_version,
        device.hardware_version,
    )


def _register_device_info_polling(
    hass: HomeAssistant,
    entry: ZentralyConfigEntry,
    device: ZentralyDevice,
    device_registry: dr.DeviceRegistry,
    registry_device_id: str,
) -> None:
    """Register periodic device-information polling when supported."""

    if not device.supports_device_info:
        return

    refresh_task: asyncio.Task[None] | None = None

    @callback
    def _async_schedule_device_info_refresh(now: datetime | None = None) -> None:
        """Schedule one metadata read, owned by the config entry."""
        nonlocal refresh_task
        if not device.connected or (
            refresh_task is not None and not refresh_task.done()
        ):
            return
        refresh_task = entry.async_create_background_task(
            hass,
            _async_refresh_device_info(device, device_registry, registry_device_id),
            f"Refresh Zentraly device information: {device.device_id}",
        )

    @callback
    def _async_connection_changed(connected: bool) -> None:
        """Refresh metadata after a connection is established."""
        if connected:
            _async_schedule_device_info_refresh()

    entry.async_on_unload(
        device.add_connection_state_listener(_async_connection_changed)
    )
    entry.async_on_unload(
        async_track_time_interval(
            hass,
            _async_schedule_device_info_refresh,
            DEVICE_INFO_INTERVAL,
        )
    )
    _async_schedule_device_info_refresh()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ZentralyConfigEntry,
) -> bool:
    """Set up Zentraly from a config entry."""

    device_id = entry.data[CONF_DEVICE_ID]

    api = ZentralyApi(
        session=async_get_clientsession(hass),
        mac=entry.data[CONF_MAC],
        host=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        password=entry.data[CONF_PASSWORD],
        device_id=device_id,
    )

    try:
        mac = await api.async_validate_password()

    except ZentralyAuthenticationError as err:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="authentication_failed",
            translation_placeholders={"device_id": api.device_id},
        ) from err

    except ZentralyConnectionError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="setup_cannot_connect",
            translation_placeholders={"device_id": api.device_id},
        ) from err

    if mac != entry.data[CONF_MAC]:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="unexpected_device",
            translation_placeholders={"host": api.host},
        )

    device = create_device(
        api=api,
        device_id=device_id,
        mac=entry.data[CONF_MAC],
    )

    device_registry = dr.async_get(hass)

    parent_device_entry = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        **device.device_info,
    )

    runtime_data = ZentralyData(api=api, device=device)
    platforms = [Platform.CLIMATE]

    # Connection failures are retried inside the library's background task.
    await api.async_connect()
    entry.async_on_unload(api.async_disconnect)

    entry.runtime_data = runtime_data

    _register_device_info_polling(
        hass,
        entry,
        device,
        device_registry,
        parent_device_entry.id,
    )

    await hass.config_entries.async_forward_entry_setups(
        entry,
        platforms,
    )

    _LOGGER.info(
        "Zentraly device created in Home Assistant: device_id=%s mac=%s ip=%s",
        device.device_id,
        device.mac,
        api.host,
    )

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: ZentralyConfigEntry,
) -> bool:
    """Unload a Zentraly config entry."""

    platforms = [Platform.CLIMATE]

    return await hass.config_entries.async_unload_platforms(
        entry,
        platforms,
    )
