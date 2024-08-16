"""Support for LG ThinQ Connect device."""

from __future__ import annotations

import asyncio
from collections.abc import Collection
from dataclasses import dataclass, field
import logging
import uuid

from thinqconnect.thinq_api import ThinQApiResponse

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_COUNTRY, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CLIENT_PREFIX, CONF_CONNECT_CLIENT_ID, DEFAULT_COUNTRY, DOMAIN
from .device import LGDevice, async_setup_lg_device
from .thinq import ThinQ

type ThinqConfigEntry = ConfigEntry[ThinqData]


@dataclass(kw_only=True)
class ThinqData:
    """A class that holds runtime data."""

    device_map: dict[str, LGDevice] = field(default_factory=dict)


PLATFORMS = [Platform.SWITCH]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ThinqConfigEntry) -> bool:
    """Set up an entry."""

    # Validate entry data.
    client_id = entry.data.get(CONF_CONNECT_CLIENT_ID)
    if not isinstance(client_id, str):
        client_id = f"{CLIENT_PREFIX}-{uuid.uuid4()!s}"
    access_token = entry.data.get(CONF_ACCESS_TOKEN)
    if not isinstance(access_token, str):
        raise ConfigEntryAuthFailed(f"Invalid PAT: {access_token}")

    # Initialize runtime data.
    entry.runtime_data = ThinqData()

    thinq = ThinQ(
        client_session=async_get_clientsession(hass),
        country_code=entry.data.get(CONF_COUNTRY, DEFAULT_COUNTRY),
        client_id=client_id,
        access_token=access_token,
    )
    device_registry = dr.async_get(hass)

    # Setup and register devices.
    await async_setup_devices(hass, thinq, device_registry, entry)

    # Set up all platforms for this device/entry.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Clean up devices they are no longer in use.
    async_cleanup_device_registry(
        entry.runtime_data.device_map.values(), device_registry, entry.entry_id
    )

    return True


async def async_setup_devices(
    hass: HomeAssistant,
    thinq: ThinQ,
    device_registry: dr.DeviceRegistry,
    entry: ThinqConfigEntry,
) -> None:
    """Set up and register devices."""
    entry.runtime_data.device_map.clear()

    # Get a device list from the server.
    response: ThinQApiResponse = await thinq.async_get_device_list()
    if not ThinQ.is_success(response):
        raise ConfigEntryError(
            response.error_message,
            translation_domain=DOMAIN,
            translation_key=response.error_code,
        )

    device_list = response.body
    if not device_list or not isinstance(device_list, Collection):
        return

    # Setup devices.
    lg_device_list: list[LGDevice] = []
    task_list = [
        hass.async_create_task(async_setup_lg_device(hass, thinq, device))
        for device in device_list
    ]
    if task_list:
        task_result = await asyncio.gather(*task_list)
        for lg_devices in task_result:
            if lg_devices:
                lg_device_list.extend(lg_devices)

    # Register devices.
    async_register_devices(lg_device_list, device_registry, entry)


@callback
def async_register_devices(
    lg_device_list: list[LGDevice],
    device_registry: dr.DeviceRegistry,
    entry: ThinqConfigEntry,
) -> None:
    """Register devices to the device registry."""
    for lg_device in lg_device_list:
        device_entry = device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            **lg_device.device_info,
        )
        _LOGGER.debug(
            "Register device: device_id=%s, device_entry_id=%s",
            lg_device.id,
            device_entry.id,
        )
        entry.runtime_data.device_map[device_entry.id] = lg_device


@callback
def async_cleanup_device_registry(
    lg_devices: Collection[LGDevice],
    device_registry: dr.DeviceRegistry,
    entry_id: str,
) -> None:
    """Clean up device registry."""
    new_device_unique_ids: list[str] = [device.unique_id for device in lg_devices]
    existing_entries: list[dr.DeviceEntry] = dr.async_entries_for_config_entry(
        device_registry, entry_id
    )

    # Remove devices that are no longer exist.
    for old_entry in existing_entries:
        old_unique_id = next(iter(old_entry.identifiers))[1]
        if old_unique_id not in new_device_unique_ids:
            device_registry.async_remove_device(old_entry.id)
            _LOGGER.debug("Remove device_registry: device_id=%s", old_entry.id)


async def async_unload_entry(hass: HomeAssistant, entry: ThinqConfigEntry) -> bool:
    """Unload the entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
