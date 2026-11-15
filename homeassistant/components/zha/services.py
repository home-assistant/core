"""Support for Zigbee Home Automation services."""

import logging
from typing import Any, cast

import probatio
from zha.application.const import (
    ATTR_ARGS,
    ATTR_ATTRIBUTE,
    ATTR_CLUSTER_ID,
    ATTR_CLUSTER_TYPE,
    ATTR_COMMAND_TYPE,
    ATTR_ENDPOINT_ID,
    ATTR_MANUFACTURER,
    ATTR_PARAMS,
    ATTR_VALUE,
    CLUSTER_TYPE_IN,
)
from zha.application.gateway import Gateway
from zha.application.platforms.siren import (
    BaseSiren,
    SirenLevel,
    SquawkMode,
    Strobe,
    StrobeLevel,
    WarningMode,
)
from zha.zigbee.device import ZigbeeDevice
from zigpy.types.named import EUI64, KeyData
from zigpy.typing import (
    UNDEFINED as ZIGPY_UNDEFINED,
    UndefinedType as ZigpyUndefinedType,
)

from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN
from homeassistant.const import ATTR_COMMAND, Platform
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import (
    async_register_admin_service,
    async_register_platform_entity_service,
)
from homeassistant.helpers.typing import VolDictType, VolSchemaType

from .const import (
    DOMAIN,
    MFG_CLUSTER_ID_START,
    RESPONSE,
    ZHAService,
    ZHAServiceArgument,
)
from .helpers import IEEE_SCHEMA, SERVICE_PERMIT_PARAMS, get_zha_data

_LOGGER = logging.getLogger(__name__)

ATTR_IEEE_ADDRESS = "ieee_address"


IEEE_SERVICE = "ieee_based_service"


def _ensure_list_if_present[_T](value: _T | None) -> list[_T] | list[Any] | None:
    """Wrap value in list if it is provided and not one."""
    if value is None:
        return None
    return cast("list[_T]", value) if isinstance(value, list) else [value]


SERVICE_SCHEMAS: dict[str, VolSchemaType] = {
    ZHAService.PERMIT: probatio.Schema(
        probatio.All(
            cv.deprecated(ATTR_IEEE_ADDRESS, replacement_key=ZHAServiceArgument.IEEE),
            SERVICE_PERMIT_PARAMS,
        )
    ),
    IEEE_SERVICE: probatio.Schema(
        probatio.All(
            cv.deprecated(ATTR_IEEE_ADDRESS, replacement_key=ZHAServiceArgument.IEEE),
            {probatio.Required(ZHAServiceArgument.IEEE): IEEE_SCHEMA},
        )
    ),
    ZHAService.SET_ZIGBEE_CLUSTER_ATTRIBUTE: probatio.Schema(
        {
            probatio.Required(ZHAServiceArgument.IEEE): IEEE_SCHEMA,
            probatio.Required(ZHAServiceArgument.ENDPOINT_ID): cv.positive_int,
            probatio.Required(ZHAServiceArgument.CLUSTER_ID): cv.positive_int,
            probatio.Optional(
                ZHAServiceArgument.CLUSTER_TYPE, default=CLUSTER_TYPE_IN
            ): cv.string,
            probatio.Required(ZHAServiceArgument.ATTRIBUTE): probatio.Any(
                cv.positive_int, str
            ),
            probatio.Required(ZHAServiceArgument.VALUE): probatio.Any(
                int, cv.boolean, cv.string
            ),
            probatio.Optional(ZHAServiceArgument.MANUFACTURER): probatio.All(
                probatio.Coerce(int), probatio.Range(min=-1)
            ),
        }
    ),
    ZHAService.WARNING_DEVICE_SQUAWK: probatio.Schema(
        {
            probatio.Required(ZHAServiceArgument.IEEE): IEEE_SCHEMA,
            probatio.Optional(
                ZHAServiceArgument.MODE, default=SquawkMode.Armed
            ): cv.positive_int,
            probatio.Optional(
                ZHAServiceArgument.STROBE, default=Strobe.Strobe
            ): cv.positive_int,
            probatio.Optional(
                ZHAServiceArgument.LEVEL, default=SirenLevel.High_level_sound
            ): cv.positive_int,
        }
    ),
    ZHAService.WARNING_DEVICE_WARN: probatio.Schema(
        {
            probatio.Required(ZHAServiceArgument.IEEE): IEEE_SCHEMA,
            probatio.Optional(
                ZHAServiceArgument.MODE, default=WarningMode.Emergency
            ): cv.positive_int,
            probatio.Optional(
                ZHAServiceArgument.STROBE, default=Strobe.Strobe
            ): cv.positive_int,
            probatio.Optional(
                ZHAServiceArgument.LEVEL, default=SirenLevel.High_level_sound
            ): cv.positive_int,
            probatio.Optional(ZHAServiceArgument.DURATION, default=5): cv.positive_int,
            probatio.Optional(
                ZHAServiceArgument.DUTY_CYCLE, default=0x00
            ): cv.positive_int,
            probatio.Optional(
                ZHAServiceArgument.INTENSITY,
                default=StrobeLevel.High_level_strobe,
            ): cv.positive_int,
        }
    ),
    ZHAService.ISSUE_ZIGBEE_CLUSTER_COMMAND: probatio.All(
        probatio.Schema(
            {
                probatio.Required(ZHAServiceArgument.IEEE): IEEE_SCHEMA,
                probatio.Required(ZHAServiceArgument.ENDPOINT_ID): cv.positive_int,
                probatio.Required(ZHAServiceArgument.CLUSTER_ID): cv.positive_int,
                probatio.Optional(
                    ZHAServiceArgument.CLUSTER_TYPE, default=CLUSTER_TYPE_IN
                ): cv.string,
                probatio.Required(ZHAServiceArgument.COMMAND): cv.positive_int,
                probatio.Required(ZHAServiceArgument.COMMAND_TYPE): cv.string,
                probatio.Exclusive(
                    ZHAServiceArgument.ARGS, "attrs_params"
                ): _ensure_list_if_present,
                probatio.Exclusive(ZHAServiceArgument.PARAMS, "attrs_params"): dict,
                probatio.Optional(ZHAServiceArgument.MANUFACTURER): probatio.All(
                    probatio.Coerce(int), probatio.Range(min=-1)
                ),
            }
        ),
        cv.deprecated(ZHAServiceArgument.ARGS),
        probatio.AtLeastOne(ZHAServiceArgument.ARGS, ZHAServiceArgument.PARAMS),
    ),
    ZHAService.ISSUE_ZIGBEE_GROUP_COMMAND: probatio.Schema(
        {
            probatio.Required(ZHAServiceArgument.GROUP): cv.positive_int,
            probatio.Required(ZHAServiceArgument.CLUSTER_ID): cv.positive_int,
            probatio.Optional(
                ZHAServiceArgument.CLUSTER_TYPE, default=CLUSTER_TYPE_IN
            ): cv.string,
            probatio.Required(ZHAServiceArgument.COMMAND): cv.positive_int,
            probatio.Optional(
                ZHAServiceArgument.ARGS, default=[]
            ): probatio.EnsureList(),
            probatio.Optional(ZHAServiceArgument.MANUFACTURER): probatio.All(
                probatio.Coerce(int), probatio.Range(min=-1)
            ),
        }
    ),
}


def _get_gateway(service: ServiceCall) -> Gateway:
    """Return the ZHA gateway, raising a user-facing error if it is unavailable."""
    if (gateway_proxy := get_zha_data(service.hass).gateway_proxy) is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="no_gateway",
        )

    return gateway_proxy.gateway


def _get_zigbee_device(zha_gateway: Gateway, ieee: EUI64) -> ZigbeeDevice:
    """Return the Zigbee device, raising if it is missing or not a Zigbee device."""
    zha_device = zha_gateway.get_device(ieee)
    if zha_device is None:
        raise ValueError(f"Device with IEEE {ieee!s} not found")

    if not isinstance(zha_device, ZigbeeDevice):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="not_zigbee_device",
            translation_placeholders={"ieee": str(ieee)},
        )

    return zha_device


async def _permit(service: ServiceCall) -> None:
    """Allow devices to join this network."""
    application_controller = _get_gateway(service).application_controller
    duration: int = service.data[ZHAServiceArgument.DURATION]
    ieee: EUI64 | None = service.data.get(ZHAServiceArgument.IEEE)
    src_ieee: EUI64
    link_key: KeyData
    if ZHAServiceArgument.SOURCE_IEEE in service.data:
        src_ieee = service.data[ZHAServiceArgument.SOURCE_IEEE]
        link_key = service.data[ZHAServiceArgument.INSTALL_CODE]
        _LOGGER.info("Allowing join for %s device with link key", src_ieee)
        await application_controller.permit_with_link_key(
            time_s=duration, node=src_ieee, link_key=link_key
        )
        return

    if ZHAServiceArgument.QR_CODE in service.data:
        src_ieee, link_key = service.data[ZHAServiceArgument.QR_CODE]
        _LOGGER.info("Allowing join for %s device with link key", src_ieee)
        await application_controller.permit_with_link_key(
            time_s=duration, node=src_ieee, link_key=link_key
        )
        return

    if ieee:
        _LOGGER.info("Permitting joins for %ss on %s device", duration, ieee)
    else:
        _LOGGER.info("Permitting joins for %ss", duration)
    await application_controller.permit(time_s=duration, node=ieee)


async def _remove(service: ServiceCall) -> None:
    """Remove a node from the network."""
    zha_gateway = _get_gateway(service)
    ieee: EUI64 = service.data[ZHAServiceArgument.IEEE]
    _LOGGER.info("Removing node %s", ieee)
    await zha_gateway.async_remove_device(ieee)


async def _set_zigbee_cluster_attributes(service: ServiceCall) -> None:
    """Set zigbee attribute for cluster on zha entity."""
    zha_gateway = _get_gateway(service)
    ieee: EUI64 = service.data[ZHAServiceArgument.IEEE]
    endpoint_id: int = service.data[ZHAServiceArgument.ENDPOINT_ID]
    cluster_id: int = service.data[ZHAServiceArgument.CLUSTER_ID]
    cluster_type: str = service.data[ZHAServiceArgument.CLUSTER_TYPE]
    attribute: int | str = service.data[ZHAServiceArgument.ATTRIBUTE]
    value: int | bool | str = service.data[ZHAServiceArgument.VALUE]
    manufacturer: int | ZigpyUndefinedType = service.data.get(
        ZHAServiceArgument.MANUFACTURER, ZIGPY_UNDEFINED
    )
    zha_device = _get_zigbee_device(zha_gateway, ieee)
    response = await zha_device.write_zigbee_attribute(
        endpoint_id,
        cluster_id,
        attribute,
        value,
        cluster_type=cluster_type,
        manufacturer=manufacturer,
    )

    _LOGGER.debug(
        (
            "Set attribute for: %s: [%s] %s: [%s] %s: [%s] %s: [%s] %s: [%s] %s:"
            " [%s] %s: [%s]"
        ),
        ATTR_CLUSTER_ID,
        cluster_id,
        ATTR_CLUSTER_TYPE,
        cluster_type,
        ATTR_ENDPOINT_ID,
        endpoint_id,
        ATTR_ATTRIBUTE,
        attribute,
        ATTR_VALUE,
        value,
        ATTR_MANUFACTURER,
        manufacturer,
        RESPONSE,
        response,
    )


async def _issue_zigbee_cluster_command(service: ServiceCall) -> None:
    """Issue command on zigbee cluster on ZHA entity."""
    zha_gateway = _get_gateway(service)
    ieee: EUI64 = service.data[ZHAServiceArgument.IEEE]
    endpoint_id: int = service.data[ZHAServiceArgument.ENDPOINT_ID]
    cluster_id: int = service.data[ZHAServiceArgument.CLUSTER_ID]
    cluster_type: str = service.data[ZHAServiceArgument.CLUSTER_TYPE]
    command: int = service.data[ZHAServiceArgument.COMMAND]
    command_type: str = service.data[ZHAServiceArgument.COMMAND_TYPE]
    args: list | None = service.data.get(ZHAServiceArgument.ARGS)
    params: dict | None = service.data.get(ZHAServiceArgument.PARAMS)
    manufacturer: int | ZigpyUndefinedType = service.data.get(
        ZHAServiceArgument.MANUFACTURER, ZIGPY_UNDEFINED
    )
    zha_device = _get_zigbee_device(zha_gateway, ieee)
    if cluster_id >= MFG_CLUSTER_ID_START and manufacturer is None:
        manufacturer = zha_device.manufacturer_code

    await zha_device.issue_cluster_command(
        endpoint_id,
        cluster_id,
        command,
        command_type,
        args,
        params,
        cluster_type=cluster_type,
        manufacturer=manufacturer,
    )
    _LOGGER.debug(
        (
            "Issued command for: %s: [%s] %s: [%s] %s: [%s] %s: [%s] %s: [%s]"
            " %s: [%s] %s: [%s] %s: [%s]"
        ),
        ATTR_CLUSTER_ID,
        cluster_id,
        ATTR_CLUSTER_TYPE,
        cluster_type,
        ATTR_ENDPOINT_ID,
        endpoint_id,
        ATTR_COMMAND,
        command,
        ATTR_COMMAND_TYPE,
        command_type,
        ATTR_ARGS,
        args,
        ATTR_PARAMS,
        params,
        ATTR_MANUFACTURER,
        manufacturer,
    )


async def _issue_zigbee_group_command(service: ServiceCall) -> None:
    """Issue command on zigbee cluster on a zigbee group."""
    zha_gateway = _get_gateway(service)
    group_id: int = service.data[ZHAServiceArgument.GROUP]
    cluster_id: int = service.data[ZHAServiceArgument.CLUSTER_ID]
    command: int = service.data[ZHAServiceArgument.COMMAND]
    args: list = service.data[ZHAServiceArgument.ARGS]
    manufacturer: int | ZigpyUndefinedType = service.data.get(
        ZHAServiceArgument.MANUFACTURER, ZIGPY_UNDEFINED
    )
    group = zha_gateway.get_group(group_id)
    if cluster_id >= MFG_CLUSTER_ID_START and manufacturer is None:
        _LOGGER.error("Missing manufacturer attribute for cluster: %d", cluster_id)
    response = None
    if group is not None:
        cluster = group.endpoint[cluster_id]
        response = await cluster.command(
            command, *args, manufacturer=manufacturer, expect_reply=True
        )
    _LOGGER.debug(
        "Issued group command for: %s: [%s] %s: [%s] %s: %s %s: [%s] %s: %s",
        ATTR_CLUSTER_ID,
        cluster_id,
        ATTR_COMMAND,
        command,
        ATTR_ARGS,
        args,
        ATTR_MANUFACTURER,
        manufacturer,
        RESPONSE,
        response,
    )


async def _warning_device_squawk(service: ServiceCall) -> None:
    """Issue the squawk command for an IAS warning device."""
    zha_gateway = _get_gateway(service)
    ieee: EUI64 = service.data[ZHAServiceArgument.IEEE]
    mode: int = service.data[ZHAServiceArgument.MODE]
    strobe: int = service.data[ZHAServiceArgument.STROBE]
    level: int = service.data[ZHAServiceArgument.LEVEL]

    device = zha_gateway.get_device(ieee)
    siren: BaseSiren = device.get_entity(Platform.SIREN, pick_first=True)

    await siren.async_squawk(mode=mode, strobe=strobe, squawk_level=level)


async def _warning_device_warn(service: ServiceCall) -> None:
    """Issue the warning command for an IAS warning device."""
    zha_gateway = _get_gateway(service)
    ieee: EUI64 = service.data[ZHAServiceArgument.IEEE]
    mode: int = service.data[ZHAServiceArgument.MODE]
    strobe: int = service.data[ZHAServiceArgument.STROBE]
    level: int = service.data[ZHAServiceArgument.LEVEL]
    duration: int = service.data[ZHAServiceArgument.DURATION]
    duty_mode: int = service.data[ZHAServiceArgument.DUTY_CYCLE]
    intensity: int = service.data[ZHAServiceArgument.INTENSITY]

    device = zha_gateway.get_device(ieee)
    siren: BaseSiren = device.get_entity(Platform.SIREN, pick_first=True)

    await siren.async_turn_on(
        tone=mode,
        volume_level=level,
        duration=duration,
        strobe=strobe,
        strobe_duty_cycle=duty_mode,
        strobe_intensity=intensity,
    )


LOCK_CODE_SLOT_SCHEMA: VolDictType = {
    probatio.Required(ZHAServiceArgument.CODE_SLOT): probatio.Coerce(int)
}

LOCK_SET_USER_CODE_SCHEMA: VolDictType = {
    **LOCK_CODE_SLOT_SCHEMA,
    probatio.Required(ZHAServiceArgument.USER_CODE): cv.string,
}


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the ZHA services."""
    async_register_admin_service(
        hass,
        DOMAIN,
        ZHAService.PERMIT,
        _permit,
        schema=SERVICE_SCHEMAS[ZHAService.PERMIT],
    )
    async_register_admin_service(
        hass, DOMAIN, ZHAService.REMOVE, _remove, schema=SERVICE_SCHEMAS[IEEE_SERVICE]
    )
    async_register_admin_service(
        hass,
        DOMAIN,
        ZHAService.SET_ZIGBEE_CLUSTER_ATTRIBUTE,
        _set_zigbee_cluster_attributes,
        schema=SERVICE_SCHEMAS[ZHAService.SET_ZIGBEE_CLUSTER_ATTRIBUTE],
    )
    async_register_admin_service(
        hass,
        DOMAIN,
        ZHAService.ISSUE_ZIGBEE_CLUSTER_COMMAND,
        _issue_zigbee_cluster_command,
        schema=SERVICE_SCHEMAS[ZHAService.ISSUE_ZIGBEE_CLUSTER_COMMAND],
    )
    async_register_admin_service(
        hass,
        DOMAIN,
        ZHAService.ISSUE_ZIGBEE_GROUP_COMMAND,
        _issue_zigbee_group_command,
        schema=SERVICE_SCHEMAS[ZHAService.ISSUE_ZIGBEE_GROUP_COMMAND],
    )
    async_register_admin_service(
        hass,
        DOMAIN,
        ZHAService.WARNING_DEVICE_SQUAWK,
        _warning_device_squawk,
        schema=SERVICE_SCHEMAS[ZHAService.WARNING_DEVICE_SQUAWK],
    )
    async_register_admin_service(
        hass,
        DOMAIN,
        ZHAService.WARNING_DEVICE_WARN,
        _warning_device_warn,
        schema=SERVICE_SCHEMAS[ZHAService.WARNING_DEVICE_WARN],
    )

    for service_name, func in (
        (ZHAService.ENABLE_LOCK_USER_CODE, "async_enable_lock_user_code"),
        (ZHAService.DISABLE_LOCK_USER_CODE, "async_disable_lock_user_code"),
        (ZHAService.CLEAR_LOCK_USER_CODE, "async_clear_lock_user_code"),
    ):
        async_register_platform_entity_service(
            hass,
            DOMAIN,
            service_name,
            entity_domain=LOCK_DOMAIN,
            schema=LOCK_CODE_SLOT_SCHEMA,
            func=func,
        )

    async_register_platform_entity_service(
        hass,
        DOMAIN,
        ZHAService.SET_LOCK_USER_CODE,
        entity_domain=LOCK_DOMAIN,
        schema=LOCK_SET_USER_CODE_SCHEMA,
        func="async_set_lock_user_code",
    )
