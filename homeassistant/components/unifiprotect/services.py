"""UniFi Protect Integration services."""
from __future__ import annotations

import functools

from pydantic import ValidationError
from pyunifiprotect.exceptions import BadRequest
import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.service import async_extract_referenced_entity_ids

from .const import ATTR_MESSAGE, DOMAIN
from .data import ProtectData

SERVICE_ADD_DOORBELL_TEXT = "add_doorbell_text"
SERVICE_REMOVE_DOORBELL_TEXT = "remove_doorbell_text"
SERVICE_SET_DEFAULT_DOORBELL_TEXT = "set_default_doorbell_text"

ALL_GLOBAL_SERIVCES = [
    SERVICE_ADD_DOORBELL_TEXT,
    SERVICE_REMOVE_DOORBELL_TEXT,
    SERVICE_SET_DEFAULT_DOORBELL_TEXT,
]

DOORBELL_TEXT_SCHEMA = vol.All(
    vol.Schema(
        {
            **cv.ENTITY_SERVICE_FIELDS,
            vol.Required(ATTR_MESSAGE): cv.string,
        },
    ),
    cv.has_at_least_one_key(ATTR_DEVICE_ID),
)


def _async_all_ufp_instances(hass: HomeAssistant) -> list[ProtectData]:
    """All active UFP instances."""
    return [
        data for data in hass.data[DOMAIN].values() if isinstance(data, ProtectData)
    ]


@callback
def _async_get_ufp_instance(hass: HomeAssistant, device_id: str) -> ProtectData:
    device_registry = dr.async_get(hass)
    if not (device_entry := device_registry.async_get(device_id)):
        raise HomeAssistantError(f"No device found for device id: {device_id}")

    if device_entry.via_device_id is not None:
        return _async_get_ufp_instance(hass, device_entry.via_device_id)

    ufp_instances = [
        i
        for i in _async_all_ufp_instances(hass)
        if i.async_get_ufp_device_from_device(device_id) is not None
    ]

    if not ufp_instances:
        raise HomeAssistantError(
            f"No UniFi Protect Config Entry found for device ID: {device_id}"
        )

    return ufp_instances[0]


@callback
def _async_get_protect_from_call(
    hass: HomeAssistant, call: ServiceCall
) -> tuple[ProtectData, str]:
    referenced = async_extract_referenced_entity_ids(hass, call)

    if len(referenced.referenced_devices) == 0:
        raise HomeAssistantError("No referenced devices")  # pragma: no cover

    device_id = referenced.referenced_devices.pop()
    return _async_get_ufp_instance(hass, device_id), device_id


async def add_doorbell_text(hass: HomeAssistant, call: ServiceCall) -> None:
    """Add a custom doorbell text message."""
    message: str = call.data[ATTR_MESSAGE]
    instance, _ = _async_get_protect_from_call(hass, call)
    try:
        await instance.api.bootstrap.nvr.add_custom_doorbell_message(message)
    except (BadRequest, ValidationError) as err:
        raise HomeAssistantError(str(err)) from err


async def remove_doorbell_text(hass: HomeAssistant, call: ServiceCall) -> None:
    """Remove a custom doorbell text message."""
    message: str = call.data[ATTR_MESSAGE]
    instance, _ = _async_get_protect_from_call(hass, call)
    try:
        await instance.api.bootstrap.nvr.remove_custom_doorbell_message(message)
    except (BadRequest, ValidationError) as err:
        raise HomeAssistantError(str(err)) from err


async def set_default_doorbell_text(hass: HomeAssistant, call: ServiceCall) -> None:
    """Set the default doorbell text message."""
    message: str = call.data[ATTR_MESSAGE]
    instance, _ = _async_get_protect_from_call(hass, call)
    try:
        await instance.api.bootstrap.nvr.set_default_doorbell_message(message)
    except (BadRequest, ValidationError) as err:
        raise HomeAssistantError(str(err)) from err


def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the global UniFi Protect services."""
    services = [
        (
            SERVICE_ADD_DOORBELL_TEXT,
            functools.partial(add_doorbell_text, hass),
            DOORBELL_TEXT_SCHEMA,
        ),
        (
            SERVICE_REMOVE_DOORBELL_TEXT,
            functools.partial(remove_doorbell_text, hass),
            DOORBELL_TEXT_SCHEMA,
        ),
        (
            SERVICE_SET_DEFAULT_DOORBELL_TEXT,
            functools.partial(set_default_doorbell_text, hass),
            DOORBELL_TEXT_SCHEMA,
        ),
    ]
    for name, method, schema in services:
        if hass.services.has_service(DOMAIN, name):
            continue
        hass.services.async_register(DOMAIN, name, method, schema=schema)


def async_cleanup_services(hass: HomeAssistant) -> None:
    """Cleanup global UniFi Protect services (if all config entries unloaded)."""
    loaded_entries = [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.state == ConfigEntryState.LOADED
    ]
    if len(loaded_entries) == 1:
        for name in ALL_GLOBAL_SERIVCES:
            hass.services.async_remove(DOMAIN, name)
