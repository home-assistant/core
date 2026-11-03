"""UniFi Protect Integration services."""

import asyncio
from collections.abc import Callable, Coroutine
import logging
from typing import Any, cast

import probatio
from pydantic import ValidationError
from uiprotect.api import ProtectApiClient
from uiprotect.data import Camera, ModelType
from uiprotect.data.public_bootstrap import PublicBootstrap
from uiprotect.data.public_devices import PublicCamera, PublicChime
from uiprotect.exceptions import ClientError
from uiprotect.utils import normalize_mac

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.event import EventDeviceClass
from homeassistant.const import (
    ATTR_CONFIG_ENTRY_ID,
    ATTR_DEVICE_ID,
    ATTR_NAME,
    Platform,
)
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
    service,
)
from homeassistant.helpers.target import (
    TargetSelection,
    async_extract_referenced_entity_ids,
)
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
from .data import UFPConfigEntry

_LOGGER = logging.getLogger(__name__)

SERVICE_ADD_DOORBELL_TEXT = "add_doorbell_text"
SERVICE_REMOVE_DOORBELL_TEXT = "remove_doorbell_text"
SERVICE_REMOVE_PRIVACY_ZONE = "remove_privacy_zone"
SERVICE_SET_CHIME_PAIRED = "set_chime_paired_doorbells"
SERVICE_GET_USER_KEYRING_INFO = "get_user_keyring_info"
SERVICE_PTZ_GOTO_PRESET = "ptz_goto_preset"
SERVICE_TRIGGER_ALARM_WEBHOOK = "trigger_alarm_webhook"

ATTR_PRESET = "preset"
ATTR_TRIGGER_ID = "trigger_id"

DOORBELL_TEXT_SCHEMA = probatio.Schema(
    {
        probatio.Required(ATTR_DEVICE_ID): str,
        probatio.Required(ATTR_MESSAGE): cv.string,
    },
)

CHIME_PAIRED_SCHEMA = probatio.Schema(
    {
        probatio.Required(ATTR_DEVICE_ID): str,
        "doorbells": cv.ENTITY_SERVICE_FIELDS,
    },
)

REMOVE_PRIVACY_ZONE_SCHEMA = probatio.Schema(
    {
        probatio.Required(ATTR_DEVICE_ID): str,
        probatio.Required(ATTR_NAME): cv.string,
    },
)

GET_USER_KEYRING_INFO_SCHEMA = probatio.Schema(
    {
        probatio.Required(ATTR_DEVICE_ID): str,
    },
)

PTZ_GOTO_PRESET_SCHEMA = probatio.Schema(
    {
        probatio.Required(ATTR_DEVICE_ID): str,
        probatio.Required(ATTR_PRESET): cv.string,
    },
)

TRIGGER_ALARM_WEBHOOK_SCHEMA = probatio.Schema(
    {
        probatio.Required(ATTR_CONFIG_ENTRY_ID): str,
        probatio.Required(ATTR_TRIGGER_ID): probatio.All(
            cv.string, probatio.Length(min=1)
        ),
    },
)


@callback
def _async_get_ufp_instance(hass: HomeAssistant, device_id: str) -> ProtectApiClient:
    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get(device_id)

    if isinstance(device_entry, dr.ChildDeviceEntry):
        return _async_get_ufp_instance(hass, device_entry.parent_device_id)

    if device_entry is not None and device_entry.via_device_id is not None:
        return _async_get_ufp_instance(hass, device_entry.via_device_id)

    _, config_entry = service.async_get_device_and_config_entry(hass, DOMAIN, device_id)
    ufp_instance = cast(UFPConfigEntry, config_entry).runtime_data.api
    if ufp_instance.is_public_only:
        # Actions read/write through the private bootstrap, which an
        # API-key-only entry never initializes.
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="public_only_no_actions",
        )
    return ufp_instance


@callback
def _async_get_ufp_camera(call: ServiceCall) -> Camera:
    ref = async_extract_referenced_entity_ids(call.hass, TargetSelection(call.data))
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
            call.hass, TargetSelection(call.data)
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
        _LOGGER.debug("Error calling UniFi Protect service: %s", err)
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="service_error",
        ) from err


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
            translation_domain=DOMAIN,
            translation_key="privacy_zone_not_found",
            translation_placeholders={
                "zone_name": name,
                "camera_name": camera.display_name,
            },
        )

    def remove_zone() -> None:
        camera.privacy_zones.pop(remove_index)

    await camera.queue_update(remove_zone)


@callback
def _async_unique_id_to_mac(unique_id: str) -> str:
    """Extract the MAC address from the registry entry unique id."""
    return unique_id.split("_", maxsplit=1)[0]


@callback
def _async_device_name(
    hass: HomeAssistant, device_id: str | None, fallback: str
) -> str:
    """Return the name of a Home Assistant device for an error message."""
    device = dr.async_get(hass).async_get(device_id) if device_id else None
    return (device and (device.name_by_user or device.name)) or fallback


@callback
def _async_device_not_available(
    hass: HomeAssistant, device_id: str | None, mac: str
) -> HomeAssistantError:
    """Return the error for a device the public API does not know."""
    return HomeAssistantError(
        translation_domain=DOMAIN,
        translation_key="device_not_available",
        translation_placeholders={
            "device_name": _async_device_name(hass, device_id, mac)
        },
    )


@callback
def _async_get_public_chime(
    hass: HomeAssistant, public_bootstrap: PublicBootstrap, device_id: str
) -> PublicChime:
    """Get the public chime of a device.

    Matched by mac, read from the device: the registries only know a Protect
    device by its mac, and other integrations can add entities to the device.
    """
    device = dr.async_get(hass).async_get(device_id, include_child_devices=False)
    macs = (
        [mac for kind, mac in device.connections if kind == dr.CONNECTION_NETWORK_MAC]
        if device
        else []
    )
    for mac in macs:
        if (
            chime := public_bootstrap.get_device_from_mac(mac, ModelType.CHIME)
        ) is not None:
            return cast(PublicChime, chime)
    nvr = public_bootstrap.nvr
    nvr_mac = normalize_mac(nvr.mac) if nvr is not None and nvr.mac else None
    if any(
        public_bootstrap.get_device_from_mac(mac) is not None
        # get_device_from_mac skips the NVR.
        or normalize_mac(mac) == nvr_mac
        for mac in macs
    ):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="not_a_chime",
            translation_placeholders={
                "device_name": _async_device_name(hass, device_id, macs[0])
            },
        )
    raise _async_device_not_available(hass, device_id, macs[0] if macs else device_id)


# The deprecated doorbell binary sensor stays accepted until it is removed.
_DOORBELL_ENTITY_CLASSES = {
    (Platform.BINARY_SENSOR, BinarySensorDeviceClass.OCCUPANCY),
    (Platform.EVENT, EventDeviceClass.DOORBELL),
}


async def set_chime_paired_doorbells(call: ServiceCall) -> None:
    """Set paired doorbells on chime."""
    chime_device_id: str = call.data[ATTR_DEVICE_ID]
    instance = _async_get_ufp_instance(call.hass, chime_device_id)
    public_bootstrap = instance.public_bootstrap
    chime = _async_get_public_chime(call.hass, public_bootstrap, chime_device_id)

    entity_registry = er.async_get(call.hass)
    call.data = ReadOnlyDict(call.data.get("doorbells") or {})
    doorbell_refs = async_extract_referenced_entity_ids(
        call.hass, TargetSelection(call.data)
    )
    doorbell_ids: set[str] = set()
    for camera_id in doorbell_refs.referenced | doorbell_refs.indirectly_referenced:
        doorbell_sensor = entity_registry.async_get(camera_id)
        assert doorbell_sensor is not None
        if (
            doorbell_sensor.platform != DOMAIN
            or (doorbell_sensor.domain, doorbell_sensor.original_device_class)
            not in _DOORBELL_ENTITY_CLASSES
        ):
            continue
        doorbell_mac = _async_unique_id_to_mac(doorbell_sensor.unique_id)
        if (
            camera := public_bootstrap.get_device_from_mac(
                doorbell_mac, ModelType.CAMERA
            )
        ) is None:
            raise _async_device_not_available(
                call.hass, doorbell_sensor.device_id, doorbell_mac
            )
        doorbell_ids.add(camera.id)
    try:
        await chime.set_camera_ids(sorted(doorbell_ids))
    except (ClientError, ValidationError) as err:
        _LOGGER.debug("Error pairing UniFi Protect chime: %s", err)
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="service_error",
        ) from err


@callback
def _async_get_ptz_camera(call: ServiceCall) -> Camera:
    """Get a PTZ camera from a service call, validating PTZ support."""
    camera = _async_get_ufp_camera(call)
    if not camera.feature_flags.is_ptz:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="not_ptz_camera",
            translation_placeholders={"camera_name": camera.display_name},
        )
    return camera


async def _async_ptz_command(
    func: Callable[..., Coroutine[Any, Any, Any]], **kwargs: Any
) -> Any:
    """Execute a PTZ command with error handling."""
    try:
        return await func(**kwargs)
    except (ClientError, ValidationError) as err:
        _LOGGER.debug("Error calling UniFi Protect PTZ command: %s", err)
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="service_error",
        ) from err


@callback
def _async_get_public_camera(camera: Camera) -> PublicCamera:
    """Get the public camera matching a private camera."""
    if (public := camera.api.public_bootstrap.cameras.get(camera.id)) is not None:
        return public
    raise HomeAssistantError(
        translation_domain=DOMAIN,
        translation_key="device_not_available",
        translation_placeholders={"device_name": camera.display_name},
    )


async def ptz_goto_preset(call: ServiceCall) -> None:
    """Move a PTZ camera to a preset position."""
    camera = _async_get_ptz_camera(call)
    public = _async_get_public_camera(camera)
    preset_name: str = call.data[ATTR_PRESET]

    if preset_name.lower() == "home":
        await _async_ptz_command(public.ptz_goto_preset, slot=-1)
        return

    presets = await _async_ptz_command(camera.get_ptz_presets)

    for preset in presets:
        if preset.name == preset_name:
            await _async_ptz_command(public.ptz_goto_preset, slot=preset.slot)
            return

    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="ptz_preset_not_found",
        translation_placeholders={
            "preset_name": preset_name,
            "camera_name": camera.display_name,
        },
    )


async def get_user_keyring_info(call: ServiceCall) -> ServiceResponse:
    """Get the user keyring info."""
    camera = _async_get_ufp_camera(call)
    ulp_users = camera.api.bootstrap.ulp_users.as_list()
    if not ulp_users:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="no_users_found",
        )

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


async def trigger_alarm_webhook(call: ServiceCall) -> None:
    """Fire an Alarm Manager webhook trigger."""
    entry: UFPConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data[ATTR_CONFIG_ENTRY_ID]
    )
    try:
        await entry.runtime_data.api.send_alarm_webhook_public(
            call.data[ATTR_TRIGGER_ID]
        )
    except ClientError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="command_error",
            translation_placeholders={"error": str(err)},
        ) from err


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
    (
        SERVICE_PTZ_GOTO_PRESET,
        ptz_goto_preset,
        PTZ_GOTO_PRESET_SCHEMA,
        SupportsResponse.NONE,
    ),
]


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the global UniFi Protect services."""

    for name, method, schema, supports_response in SERVICES:
        hass.services.async_register(
            DOMAIN, name, method, schema=schema, supports_response=supports_response
        )
    # Admin-only, there is no entity permission check.
    service.async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_TRIGGER_ALARM_WEBHOOK,
        trigger_alarm_webhook,
        schema=TRIGGER_ALARM_WEBHOOK_SCHEMA,
    )
