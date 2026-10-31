"""The Zentraly integration."""

import asyncio
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
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import UNDEFINED

from .const import DOMAIN
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

    if changed:
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


def _register_device_info_refresh(
    hass: HomeAssistant,
    entry: ZentralyConfigEntry,
    device: ZentralyDevice,
    device_registry: dr.DeviceRegistry,
    registry_device_id: str,
) -> None:
    """Refresh metadata at setup and reconnect without periodic polling."""
    if not device.supports_device_info:
        return

    refresh_task: asyncio.Task[None] | None = None

    @callback
    def _async_connection_changed(connected: bool) -> None:
        """Schedule one metadata read, owned by the config entry."""
        nonlocal refresh_task
        if (
            not connected
            or not device.connected
            or (refresh_task is not None and not refresh_task.done())
        ):
            return
        refresh_task = entry.async_create_background_task(
            hass,
            _async_refresh_device_info(device, device_registry, registry_device_id),
            f"Refresh Zentraly device information: {device.device_id}",
        )

    entry.async_on_unload(
        device.add_connection_state_listener(_async_connection_changed)
    )
    _async_connection_changed(True)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ZentralyConfigEntry,
) -> None:
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

    platforms = [Platform.CLIMATE]

    # Connection failures are retried inside the library's background task.
    await api.async_connect()
    entry.async_on_unload(api.async_disconnect)

    async def async_shutdown(event: Event) -> None:
        """Close library connection tasks before Home Assistant stops."""
        await api.async_disconnect()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_shutdown)
    )

    _register_device_info_refresh(
        hass,
        entry,
        device,
        device_registry,
        parent_device_entry.id,
    )

    entry.runtime_data = ZentralyData(api=api, device=device)

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


async def async_unload_entry(
    hass: HomeAssistant,
    entry: ZentralyConfigEntry,
) -> None:
    """Unload a Zentraly config entry."""

    platforms = [Platform.CLIMATE]

    await hass.config_entries.async_unload_platforms_or_raise(
        entry,
        platforms,
    )
