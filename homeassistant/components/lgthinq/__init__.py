"""Support for LG ThinQ Connect device."""

from __future__ import annotations

import asyncio
from collections.abc import Collection
from dataclasses import dataclass, field
import logging
from typing import Any

from thinqconnect.thinq_api import ThinQApiResponse
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_DEVICE_ID,
    CONF_ACCESS_TOKEN,
    CONF_COUNTRY,
    Platform,
)
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryError
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util.json import JsonValueType

from .const import (
    CONF_CONNECT_CLIENT_ID,
    DEFAULT_COUNTRY,
    DOMAIN,
    SERVICE_ATTR_DEVICE_INFO,
    SERVICE_ATTR_RESULT,
    SERVICE_ATTR_VALUE,
)
from .device import LGDevice, async_setup_lg_device
from .thinq import ThinQ

type ThinqConfigEntry = ConfigEntry[ThinqData]


@dataclass(kw_only=True)
class ThinqData:
    """A class that holds runtime data."""

    device_map: dict[str, LGDevice] = field(default_factory=dict)


PLATFORMS = [
    Platform.SWITCH,
]

SERVICE_GET_DEVICE_PROFILE_SCHEMA = vol.Schema(
    {vol.Required(ATTR_DEVICE_ID): cv.string}
)
SERVICE_GET_DEVICE_STATUS_SCHEMA = vol.Schema({vol.Required(ATTR_DEVICE_ID): cv.string})
SERVICE_POST_DEVICE_STATUS_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Required(SERVICE_ATTR_VALUE): vol.Any(cv.string, dict),
    }
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ThinqConfigEntry) -> bool:
    """Set up an entry."""
    _LOGGER.warning("Starting set up entry")

    # Validate entry data.
    client_id = entry.data.get(CONF_CONNECT_CLIENT_ID)
    if not isinstance(client_id, str):
        raise ConfigEntryError(f"Invalid client id: {client_id}")

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

    # Set up custom services.
    async_setup_hass_services(hass, entry)

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
    _LOGGER.warning("Starting set up devices")

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
    if lg_device_list:
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
            _LOGGER.warning("Remove device_registry: device_id=%s", old_entry.id)


@callback
def async_setup_hass_services(hass: HomeAssistant, entry: ThinqConfigEntry) -> None:
    """Set up services."""

    async def async_handle_reload_device_list(call: ServiceCall) -> None:
        """Handle 'reload_device_list' service call."""
        await hass.config_entries.async_reload(entry.entry_id)

    async def async_handle_refresh_device_status(call: ServiceCall) -> None:
        """Handle 'refresh_device_status' service call."""
        device_id = call.data.get(ATTR_DEVICE_ID)

        if device_id:
            device = entry.runtime_data.device_map.get(device_id)
            if device is not None:
                await device.coordinator.async_refresh()
        else:
            # If device_id is not specified, refresh for all devices.
            task_list = [
                hass.async_create_task(device.coordinator.async_refresh())
                for device in entry.runtime_data.device_map.values()
            ]
            await asyncio.gather(*task_list)

    async def async_handle_get_device_profile(
        call: ServiceCall,
    ) -> ServiceResponse:
        """Handle 'get_device_profile' service call."""
        device_id = call.data.get(ATTR_DEVICE_ID)
        if not device_id:
            return async_create_service_response(None, None, None)

        device = entry.runtime_data.device_map.get(device_id)
        if device is None:
            return async_create_service_response(device_id, None, None)

        result = await device.async_get_device_profile()
        return async_create_service_response(device_id, device, result)

    async def async_handle_get_device_status(
        call: ServiceCall,
    ) -> ServiceResponse:
        """Handle 'get_device_status' service call."""
        device_id = call.data.get(ATTR_DEVICE_ID)
        if not device_id:
            return async_create_service_response(None, None, None)

        device = entry.runtime_data.device_map.get(device_id)
        if device is None:
            return async_create_service_response(device_id, None, None)

        result = await device.async_get_device_status()
        return async_create_service_response(device_id, device, result)

    async def async_handle_post_device_status(
        call: ServiceCall,
    ) -> ServiceResponse:
        """Handle 'post_device_status' service call."""
        device_id = call.data.get(ATTR_DEVICE_ID)
        if not device_id:
            return async_create_service_response(None, None, None)

        device = entry.runtime_data.device_map.get(device_id)
        if device is None:
            return async_create_service_response(device_id, None, None)

        value = call.data.get(SERVICE_ATTR_VALUE)
        result = await device.async_post_device_status(value)
        return async_create_service_response(device_id, device, result)

    hass.services.async_register(
        domain=DOMAIN,
        service="reload_device_list",
        service_func=async_handle_reload_device_list,
    )
    hass.services.async_register(
        domain=DOMAIN,
        service="refresh_device_status",
        service_func=async_handle_refresh_device_status,
    )
    hass.services.async_register(
        domain=DOMAIN,
        service="get_device_profile",
        service_func=async_handle_get_device_profile,
        schema=SERVICE_GET_DEVICE_PROFILE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        domain=DOMAIN,
        service="get_device_status",
        service_func=async_handle_get_device_status,
        schema=SERVICE_GET_DEVICE_STATUS_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        domain=DOMAIN,
        service="post_device_status",
        service_func=async_handle_post_device_status,
        schema=SERVICE_POST_DEVICE_STATUS_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )


@callback
def async_create_service_response(
    device_id: str | None,
    device: LGDevice | None,
    result: dict[str, Any] | str | None,
) -> ServiceResponse:
    """Create a service response from the result of service call."""
    if result is None:
        if device_id is None:
            result = "error: No device_id specified."
        elif device is None:
            result = "error: Device not found."
        else:
            result = "error: Operation failed."

    device_info: dict[str, JsonValueType] = {}
    if device is not None:
        device_info["id"] = device.id
        device_info["sub_id"] = device.sub_id
        device_info["type"] = device.type
        device_info["name"] = device.name
        device_info["model"] = device.model

    return {
        ATTR_DEVICE_ID: device_id,
        SERVICE_ATTR_DEVICE_INFO: device_info,
        SERVICE_ATTR_RESULT: result,
    }


async def async_unload_entry(hass: HomeAssistant, entry: ThinqConfigEntry) -> bool:
    """Unload the entry."""
    _LOGGER.warning("Starting unload entry")

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
