"""UniFi Protect Integration services."""
from __future__ import annotations

import asyncio
from typing import Any

from pydantic import ValidationError
from pyunifiprotect.api import ProtectApiClient
from pyunifiprotect.exceptions import BadRequest

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.service import async_extract_referenced_entity_ids

from .const import ATTR_MESSAGE, DOMAIN
from .data import ProtectData


def _async_all_ufp_instances(hass: HomeAssistant) -> list[ProtectApiClient]:
    """All active UFP instances."""
    return [
        data.api for data in hass.data[DOMAIN].values() if isinstance(data, ProtectData)
    ]


@callback
def _async_unifi_mac_from_hass(mac: str) -> str:
    # MAC addresses in UFP are always caps
    return mac.replace(":", "").upper()


@callback
def _async_get_macs_for_device(device_entry: dr.DeviceEntry) -> list[str]:
    return [
        _async_unifi_mac_from_hass(cval)
        for ctype, cval in device_entry.connections
        if ctype == dr.CONNECTION_NETWORK_MAC
    ]


@callback
def _async_get_ufp_instances(
    hass: HomeAssistant, device_id: str
) -> tuple[dr.DeviceEntry, ProtectApiClient]:
    device_registry = dr.async_get(hass)
    if not (device_entry := device_registry.async_get(device_id)):
        raise HomeAssistantError(f"No device found for device id: {device_id}")

    if device_entry.via_device_id is not None:
        return _async_get_ufp_instances(hass, device_entry.via_device_id)

    macs = _async_get_macs_for_device(device_entry)
    ufp_instances = [
        i for i in _async_all_ufp_instances(hass) if i.bootstrap.nvr.mac in macs
    ]

    if not ufp_instances:
        # should not be possible unless user manually enters a bad device ID
        raise HomeAssistantError(  # pragma: no cover
            f"No UniFi Protect NVR found for device ID: {device_id}"
        )

    return device_entry, ufp_instances[0]


@callback
def _async_get_protect_from_call(
    hass: HomeAssistant, call: ServiceCall
) -> list[tuple[dr.DeviceEntry, ProtectApiClient]]:
    referenced = async_extract_referenced_entity_ids(hass, call)

    instances: list[tuple[dr.DeviceEntry, ProtectApiClient]] = []
    for device_id in referenced.referenced_devices:
        instances.append(_async_get_ufp_instances(hass, device_id))

    return instances


async def _async_call_nvr(
    instances: list[tuple[dr.DeviceEntry, ProtectApiClient]],
    method: str,
    *args: Any,
    **kwargs: Any,
) -> None:
    try:
        await asyncio.gather(
            *(getattr(i.bootstrap.nvr, method)(*args, **kwargs) for _, i in instances)
        )
    except (BadRequest, ValidationError) as err:
        raise HomeAssistantError(str(err)) from err


async def add_doorbell_text(hass: HomeAssistant, call: ServiceCall) -> None:
    """Add a custom doorbell text message."""
    message: str = call.data[ATTR_MESSAGE]
    instances = _async_get_protect_from_call(hass, call)
    await _async_call_nvr(instances, "add_custom_doorbell_message", message)


async def remove_doorbell_text(hass: HomeAssistant, call: ServiceCall) -> None:
    """Remove a custom doorbell text message."""
    message: str = call.data[ATTR_MESSAGE]
    instances = _async_get_protect_from_call(hass, call)
    await _async_call_nvr(instances, "remove_custom_doorbell_message", message)


async def set_default_doorbell_text(hass: HomeAssistant, call: ServiceCall) -> None:
    """Set the default doorbell text message."""
    message: str = call.data[ATTR_MESSAGE]
    instances = _async_get_protect_from_call(hass, call)
    await _async_call_nvr(instances, "set_default_doorbell_message", message)
