"""UniFi Protect Integration services."""

from __future__ import annotations

import asyncio
from typing import Any, cast

from pydantic import ValidationError
from uiprotect.api import ProtectApiClient
from uiprotect.data import Camera, Chime
from uiprotect.exceptions import ClientError
import voluptuous as vol

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.const import ATTR_DEVICE_ID, ATTR_NAME, Platform
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.service import async_extract_referenced_entity_ids
from homeassistant.util.json import JsonValueType
from homeassistant.util.read_only_dict import ReadOnlyDict

from .const import (
    ATTR_MESSAGE,
    DOMAIN,
    KEYRINGS_KEY_TYPE,
    KEYRINGS_KEY_TYPE_ID_FINGERPRINT,
    KEYRINGS_KEY_TYPE_ID_NFC,
    KEYRINGS_ULP_ID,
    KEYRINGS_USER_FULL_NAME,
    KEYRINGS_USER_STATUS,
)
from .data import async_ufp_instance_for_config_entry_ids

SERVICE_ADD_DOORBELL_TEXT = "add_doorbell_text"
SERVICE_REMOVE_DOORBELL_TEXT = "remove_doorbell_text"
SERVICE_SET_PRIVACY_ZONE = "set_privacy_zone"
SERVICE_REMOVE_PRIVACY_ZONE = "remove_privacy_zone"
SERVICE_SET_CHIME_PAIRED = "set_chime_paired_doorbells"
SERVICE_GET_USER_KEYRING_INFO = "get_user_keyring_info"

ALL_GLOBAL_SERIVCES = [
    SERVICE_ADD_DOORBELL_TEXT,
    SERVICE_REMOVE_DOORBELL_TEXT,
    SERVICE_SET_CHIME_PAIRED,
    SERVICE_REMOVE_PRIVACY_ZONE,
    SERVICE_GET_USER_KEYRING_INFO,
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

CHIME_PAIRED_SCHEMA = vol.All(
    vol.Schema(
        {
            **cv.ENTITY_SERVICE_FIELDS,
            "doorbells": cv.TARGET_SERVICE_FIELDS,
        },
    ),
    cv.has_at_least_one_key(ATTR_DEVICE_ID),
)

REMOVE_PRIVACY_ZONE_SCHEMA = vol.All(
    vol.Schema(
        {
            **cv.ENTITY_SERVICE_FIELDS,
            vol.Required(ATTR_NAME): cv.string,
        },
    ),
    cv.has_at_least_one_key(ATTR_DEVICE_ID),
)

GET_USER_KEYRING_INFO_SCHEMA = vol.All(
    vol.Schema(
        {
            **cv.ENTITY_SERVICE_FIELDS,
        },
    ),
    cv.has_at_least_one_key(ATTR_DEVICE_ID),
)


@callback
def _async_get_ufp_instance(hass: HomeAssistant, device_id: str) -> ProtectApiClient:
    device_registry = dr.async_get(hass)
    if not (device_entry := device_registry.async_get(device_id)):
        raise HomeAssistantError(f"No device found for device id: {device_id}")

    if device_entry.via_device_id is not None:
        return _async_get_ufp_instance(hass, device_entry.via_device_id)

    config_entry_ids = device_entry.config_entries
    if ufp_instance := async_ufp_instance_for_config_entry_ids(hass, config_entry_ids):
        return ufp_instance

    raise HomeAssistantError(f"No device found for device id: {device_id}")


@callback
def _async_get_ufp_camera(call: ServiceCall) -> Camera:
    ref = async_extract_referenced_entity_ids(call.hass, call)
    entity_registry = er.async_get(call.hass)

    entity_id = ref.indirectly_referenced.pop()
    camera_entity = entity_registry.async_get(entity_id)
    assert camera_entity is not None
    assert camera_entity.device_id is not None
    camera_mac = _async_unique_id_to_mac(camera_entity.unique_id)

    instance = _async_get_ufp_instance(call.hass, camera_entity.device_id)
    return cast(Camera, instance.bootstrap.get_device_from_mac(camera_mac))


@callback
def _async_get_protect_from_call(call: ServiceCall) -> set[ProtectApiClient]:
    return {
        _async_get_ufp_instance(call.hass, device_id)
        for device_id in async_extract_referenced_entity_ids(
            call.hass, call
        ).referenced_devices
    }


async def _async_service_call_nvr(
    call: ServiceCall,
    method: str,
    *args: Any,
    **kwargs: Any,
) -> None:
    instances = _async_get_protect_from_call(call)
    try:
        await asyncio.gather(
            *(getattr(i.bootstrap.nvr, method)(*args, **kwargs) for i in instances)
        )
    except (ClientError, ValidationError) as err:
        raise HomeAssistantError(str(err)) from err


async def add_doorbell_text(call: ServiceCall) -> None:
    """Add a custom doorbell text message."""
    message: str = call.data[ATTR_MESSAGE]
    await _async_service_call_nvr(call, "add_custom_doorbell_message", message)


async def remove_doorbell_text(call: ServiceCall) -> None:
    """Remove a custom doorbell text message."""
    message: str = call.data[ATTR_MESSAGE]
    await _async_service_call_nvr(call, "remove_custom_doorbell_message", message)


async def remove_privacy_zone(call: ServiceCall) -> None:
    """Remove privacy zone from camera."""

    name: str = call.data[ATTR_NAME]
    camera = _async_get_ufp_camera(call)

    remove_index: int | None = None
    for index, zone in enumerate(camera.privacy_zones):
        if zone.name == name:
            remove_index = index
            break

    if remove_index is None:
        raise ServiceValidationError(
            f"Could not find privacy zone with name {name} on camera {camera.display_name}."
        )

    def remove_zone() -> None:
        camera.privacy_zones.pop(remove_index)

    await camera.queue_update(remove_zone)


@callback
def _async_unique_id_to_mac(unique_id: str) -> str:
    """Extract the MAC address from the registry entry unique id."""
    return unique_id.split("_")[0]


async def set_chime_paired_doorbells(call: ServiceCall) -> None:
    """Set paired doorbells on chime."""
    ref = async_extract_referenced_entity_ids(call.hass, call)
    entity_registry = er.async_get(call.hass)

    entity_id = ref.indirectly_referenced.pop()
    chime_button = entity_registry.async_get(entity_id)
    assert chime_button is not None
    assert chime_button.device_id is not None
    chime_mac = _async_unique_id_to_mac(chime_button.unique_id)

    instance = _async_get_ufp_instance(call.hass, chime_button.device_id)
    chime = instance.bootstrap.get_device_from_mac(chime_mac)
    chime = cast(Chime, chime)
    assert chime is not None

    call.data = ReadOnlyDict(call.data.get("doorbells") or {})
    doorbell_refs = async_extract_referenced_entity_ids(call.hass, call)
    doorbell_ids: set[str] = set()
    for camera_id in doorbell_refs.referenced | doorbell_refs.indirectly_referenced:
        doorbell_sensor = entity_registry.async_get(camera_id)
        assert doorbell_sensor is not None
        if (
            doorbell_sensor.platform != DOMAIN
            or doorbell_sensor.domain != Platform.BINARY_SENSOR
            or doorbell_sensor.original_device_class
            != BinarySensorDeviceClass.OCCUPANCY
        ):
            continue
        doorbell_mac = _async_unique_id_to_mac(doorbell_sensor.unique_id)
        camera = instance.bootstrap.get_device_from_mac(doorbell_mac)
        assert camera is not None
        doorbell_ids.add(camera.id)
    data_before_changed = chime.dict_with_excludes()
    chime.camera_ids = sorted(doorbell_ids)
    await chime.save_device(data_before_changed)


async def get_user_keyring_info(call: ServiceCall) -> ServiceResponse:
    """Get the user keyring info."""
    camera = _async_get_ufp_camera(call)
    ulp_users = camera.api.bootstrap.ulp_users.as_list()
    if not ulp_users:
        raise HomeAssistantError("No users found, please check Protect permissions.")

    user_keyrings: list[JsonValueType] = [
        {
            KEYRINGS_USER_FULL_NAME: user.full_name,
            KEYRINGS_USER_STATUS: user.status,
            KEYRINGS_ULP_ID: user.ulp_id,
            "keys": [
                {
                    KEYRINGS_KEY_TYPE: key.registry_type,
                    **(
                        {KEYRINGS_KEY_TYPE_ID_FINGERPRINT: key.registry_id}
                        if key.registry_type == "fingerprint"
                        else {}
                    ),
                    **(
                        {KEYRINGS_KEY_TYPE_ID_NFC: key.registry_id}
                        if key.registry_type == "nfc"
                        else {}
                    ),
                }
                for key in camera.api.bootstrap.keyrings.as_list()
                if key.ulp_user == user.ulp_id
            ],
        }
        for user in ulp_users
    ]

    response: ServiceResponse = {"users": user_keyrings}
    return response


SERVICES = [
    (
        SERVICE_ADD_DOORBELL_TEXT,
        add_doorbell_text,
        DOORBELL_TEXT_SCHEMA,
        SupportsResponse.NONE,
    ),
    (
        SERVICE_REMOVE_DOORBELL_TEXT,
        remove_doorbell_text,
        DOORBELL_TEXT_SCHEMA,
        SupportsResponse.NONE,
    ),
    (
        SERVICE_SET_CHIME_PAIRED,
        set_chime_paired_doorbells,
        CHIME_PAIRED_SCHEMA,
        SupportsResponse.NONE,
    ),
    (
        SERVICE_REMOVE_PRIVACY_ZONE,
        remove_privacy_zone,
        REMOVE_PRIVACY_ZONE_SCHEMA,
        SupportsResponse.NONE,
    ),
    (
        SERVICE_GET_USER_KEYRING_INFO,
        get_user_keyring_info,
        GET_USER_KEYRING_INFO_SCHEMA,
        SupportsResponse.ONLY,
    ),
]


def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the global UniFi Protect services."""

    for name, method, schema, supports_response in SERVICES:
        hass.services.async_register(
            DOMAIN, name, method, schema=schema, supports_response=supports_response
        )
