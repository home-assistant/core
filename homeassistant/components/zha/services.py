"""Support for Zigbee Home Automation services."""

import logging
from typing import Any, cast

import voluptuous as vol
from zha.application.const import (
    ATTR_ARGS,
    ATTR_ATTRIBUTE,
    ATTR_CLUSTER_ID,
    ATTR_CLUSTER_TYPE,
    ATTR_COMMAND_TYPE,
    ATTR_ENDPOINT_ID,
    ATTR_IEEE,
    ATTR_LEVEL,
    ATTR_MANUFACTURER,
    ATTR_PARAMS,
    ATTR_VALUE,
    ATTR_WARNING_DEVICE_DURATION,
    ATTR_WARNING_DEVICE_MODE,
    ATTR_WARNING_DEVICE_STROBE,
    ATTR_WARNING_DEVICE_STROBE_DUTY_CYCLE,
    ATTR_WARNING_DEVICE_STROBE_INTENSITY,
    CLUSTER_TYPE_IN,
)
from zha.application.platforms.siren import (
    BaseSiren,
    SirenLevel,
    SquawkMode,
    Strobe,
    StrobeLevel,
    WarningMode,
)
from zigpy.types.named import EUI64, KeyData
from zigpy.typing import (
    UNDEFINED as ZIGPY_UNDEFINED,
    UndefinedType as ZigpyUndefinedType,
)

from homeassistant.const import ATTR_COMMAND, Platform
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import async_register_admin_service
from homeassistant.helpers.typing import VolSchemaType

from .const import (
    ATTR_DURATION,
    ATTR_INSTALL_CODE,
    ATTR_QR_CODE,
    ATTR_SOURCE_IEEE,
    DOMAIN,
    MFG_CLUSTER_ID_START,
    RESPONSE,
)
from .helpers import IEEE_SCHEMA, SERVICE_PERMIT_PARAMS, get_zha_gateway

_LOGGER = logging.getLogger(__name__)

ATTR_GROUP = "group"
ATTR_IEEE_ADDRESS = "ieee_address"

SERVICE_PERMIT = "permit"
SERVICE_REMOVE = "remove"
SERVICE_SET_ZIGBEE_CLUSTER_ATTRIBUTE = "set_zigbee_cluster_attribute"
SERVICE_ISSUE_ZIGBEE_CLUSTER_COMMAND = "issue_zigbee_cluster_command"
SERVICE_ISSUE_ZIGBEE_GROUP_COMMAND = "issue_zigbee_group_command"
SERVICE_WARNING_DEVICE_SQUAWK = "warning_device_squawk"
SERVICE_WARNING_DEVICE_WARN = "warning_device_warn"

IEEE_SERVICE = "ieee_based_service"


def _ensure_list_if_present[_T](value: _T | None) -> list[_T] | list[Any] | None:
    """Wrap value in list if it is provided and not one."""
    if value is None:
        return None
    return cast("list[_T]", value) if isinstance(value, list) else [value]


SERVICE_SCHEMAS: dict[str, VolSchemaType] = {
    SERVICE_PERMIT: vol.Schema(
        vol.All(
            cv.deprecated(ATTR_IEEE_ADDRESS, replacement_key=ATTR_IEEE),
            SERVICE_PERMIT_PARAMS,
        )
    ),
    IEEE_SERVICE: vol.Schema(
        vol.All(
            cv.deprecated(ATTR_IEEE_ADDRESS, replacement_key=ATTR_IEEE),
            {vol.Required(ATTR_IEEE): IEEE_SCHEMA},
        )
    ),
    SERVICE_SET_ZIGBEE_CLUSTER_ATTRIBUTE: vol.Schema(
        {
            vol.Required(ATTR_IEEE): IEEE_SCHEMA,
            vol.Required(ATTR_ENDPOINT_ID): cv.positive_int,
            vol.Required(ATTR_CLUSTER_ID): cv.positive_int,
            vol.Optional(ATTR_CLUSTER_TYPE, default=CLUSTER_TYPE_IN): cv.string,
            vol.Required(ATTR_ATTRIBUTE): vol.Any(cv.positive_int, str),
            vol.Required(ATTR_VALUE): vol.Any(int, cv.boolean, cv.string),
            vol.Optional(ATTR_MANUFACTURER): vol.All(
                vol.Coerce(int), vol.Range(min=-1)
            ),
        }
    ),
    SERVICE_WARNING_DEVICE_SQUAWK: vol.Schema(
        {
            vol.Required(ATTR_IEEE): IEEE_SCHEMA,
            vol.Optional(
                ATTR_WARNING_DEVICE_MODE, default=SquawkMode.Armed
            ): cv.positive_int,
            vol.Optional(
                ATTR_WARNING_DEVICE_STROBE, default=Strobe.Strobe
            ): cv.positive_int,
            vol.Optional(
                ATTR_LEVEL, default=SirenLevel.High_level_sound
            ): cv.positive_int,
        }
    ),
    SERVICE_WARNING_DEVICE_WARN: vol.Schema(
        {
            vol.Required(ATTR_IEEE): IEEE_SCHEMA,
            vol.Optional(
                ATTR_WARNING_DEVICE_MODE, default=WarningMode.Emergency
            ): cv.positive_int,
            vol.Optional(
                ATTR_WARNING_DEVICE_STROBE, default=Strobe.Strobe
            ): cv.positive_int,
            vol.Optional(
                ATTR_LEVEL, default=SirenLevel.High_level_sound
            ): cv.positive_int,
            vol.Optional(ATTR_WARNING_DEVICE_DURATION, default=5): cv.positive_int,
            vol.Optional(
                ATTR_WARNING_DEVICE_STROBE_DUTY_CYCLE, default=0x00
            ): cv.positive_int,
            vol.Optional(
                ATTR_WARNING_DEVICE_STROBE_INTENSITY,
                default=StrobeLevel.High_level_strobe,
            ): cv.positive_int,
        }
    ),
    SERVICE_ISSUE_ZIGBEE_CLUSTER_COMMAND: vol.All(
        vol.Schema(
            {
                vol.Required(ATTR_IEEE): IEEE_SCHEMA,
                vol.Required(ATTR_ENDPOINT_ID): cv.positive_int,
                vol.Required(ATTR_CLUSTER_ID): cv.positive_int,
                vol.Optional(ATTR_CLUSTER_TYPE, default=CLUSTER_TYPE_IN): cv.string,
                vol.Required(ATTR_COMMAND): cv.positive_int,
                vol.Required(ATTR_COMMAND_TYPE): cv.string,
                vol.Exclusive(ATTR_ARGS, "attrs_params"): _ensure_list_if_present,
                vol.Exclusive(ATTR_PARAMS, "attrs_params"): dict,
                vol.Optional(ATTR_MANUFACTURER): vol.All(
                    vol.Coerce(int), vol.Range(min=-1)
                ),
            }
        ),
        cv.deprecated(ATTR_ARGS),
        cv.has_at_least_one_key(ATTR_ARGS, ATTR_PARAMS),
    ),
    SERVICE_ISSUE_ZIGBEE_GROUP_COMMAND: vol.Schema(
        {
            vol.Required(ATTR_GROUP): cv.positive_int,
            vol.Required(ATTR_CLUSTER_ID): cv.positive_int,
            vol.Optional(ATTR_CLUSTER_TYPE, default=CLUSTER_TYPE_IN): cv.string,
            vol.Required(ATTR_COMMAND): cv.positive_int,
            vol.Optional(ATTR_ARGS, default=[]): cv.ensure_list,
            vol.Optional(ATTR_MANUFACTURER): vol.All(
                vol.Coerce(int), vol.Range(min=-1)
            ),
        }
    ),
}


async def _permit(service: ServiceCall) -> None:
    """Allow devices to join this network."""
    application_controller = get_zha_gateway(service.hass).application_controller
    duration: int = service.data[ATTR_DURATION]
    ieee: EUI64 | None = service.data.get(ATTR_IEEE)
    src_ieee: EUI64
    link_key: KeyData
    if ATTR_SOURCE_IEEE in service.data:
        src_ieee = service.data[ATTR_SOURCE_IEEE]
        link_key = service.data[ATTR_INSTALL_CODE]
        _LOGGER.info("Allowing join for %s device with link key", src_ieee)
        await application_controller.permit_with_link_key(
            time_s=duration, node=src_ieee, link_key=link_key
        )
        return

    if ATTR_QR_CODE in service.data:
        src_ieee, link_key = service.data[ATTR_QR_CODE]
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
    zha_gateway = get_zha_gateway(service.hass)
    ieee: EUI64 = service.data[ATTR_IEEE]
    _LOGGER.info("Removing node %s", ieee)
    await zha_gateway.async_remove_device(ieee)


async def _set_zigbee_cluster_attributes(service: ServiceCall) -> None:
    """Set zigbee attribute for cluster on zha entity."""
    zha_gateway = get_zha_gateway(service.hass)
    ieee: EUI64 = service.data[ATTR_IEEE]
    endpoint_id: int = service.data[ATTR_ENDPOINT_ID]
    cluster_id: int = service.data[ATTR_CLUSTER_ID]
    cluster_type: str = service.data[ATTR_CLUSTER_TYPE]
    attribute: int | str = service.data[ATTR_ATTRIBUTE]
    value: int | bool | str = service.data[ATTR_VALUE]
    manufacturer: int | ZigpyUndefinedType = service.data.get(
        ATTR_MANUFACTURER, ZIGPY_UNDEFINED
    )
    zha_device = zha_gateway.get_device(ieee)
    response = None
    if zha_device is not None:
        response = await zha_device.write_zigbee_attribute(
            endpoint_id,
            cluster_id,
            attribute,
            value,
            cluster_type=cluster_type,
            manufacturer=manufacturer,
        )
    else:
        raise ValueError(f"Device with IEEE {ieee!s} not found")

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
    zha_gateway = get_zha_gateway(service.hass)
    ieee: EUI64 = service.data[ATTR_IEEE]
    endpoint_id: int = service.data[ATTR_ENDPOINT_ID]
    cluster_id: int = service.data[ATTR_CLUSTER_ID]
    cluster_type: str = service.data[ATTR_CLUSTER_TYPE]
    command: int = service.data[ATTR_COMMAND]
    command_type: str = service.data[ATTR_COMMAND_TYPE]
    args: list | None = service.data.get(ATTR_ARGS)
    params: dict | None = service.data.get(ATTR_PARAMS)
    manufacturer: int | ZigpyUndefinedType = service.data.get(
        ATTR_MANUFACTURER, ZIGPY_UNDEFINED
    )
    zha_device = zha_gateway.get_device(ieee)
    if zha_device is not None:
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
    else:
        raise ValueError(f"Device with IEEE {ieee!s} not found")


async def _issue_zigbee_group_command(service: ServiceCall) -> None:
    """Issue command on zigbee cluster on a zigbee group."""
    zha_gateway = get_zha_gateway(service.hass)
    group_id: int = service.data[ATTR_GROUP]
    cluster_id: int = service.data[ATTR_CLUSTER_ID]
    command: int = service.data[ATTR_COMMAND]
    args: list = service.data[ATTR_ARGS]
    manufacturer: int | ZigpyUndefinedType = service.data.get(
        ATTR_MANUFACTURER, ZIGPY_UNDEFINED
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
    zha_gateway = get_zha_gateway(service.hass)
    ieee: EUI64 = service.data[ATTR_IEEE]
    mode: int = service.data[ATTR_WARNING_DEVICE_MODE]
    strobe: int = service.data[ATTR_WARNING_DEVICE_STROBE]
    level: int = service.data[ATTR_LEVEL]

    device = zha_gateway.get_device(ieee)
    siren: BaseSiren = device.get_entity(Platform.SIREN, pick_first=True)

    await siren.async_squawk(mode=mode, strobe=strobe, squawk_level=level)


async def _warning_device_warn(service: ServiceCall) -> None:
    """Issue the warning command for an IAS warning device."""
    zha_gateway = get_zha_gateway(service.hass)
    ieee: EUI64 = service.data[ATTR_IEEE]
    mode: int = service.data[ATTR_WARNING_DEVICE_MODE]
    strobe: int = service.data[ATTR_WARNING_DEVICE_STROBE]
    level: int = service.data[ATTR_LEVEL]
    duration: int = service.data[ATTR_WARNING_DEVICE_DURATION]
    duty_mode: int = service.data[ATTR_WARNING_DEVICE_STROBE_DUTY_CYCLE]
    intensity: int = service.data[ATTR_WARNING_DEVICE_STROBE_INTENSITY]

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


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the ZHA services."""
    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_PERMIT,
        _permit,
        schema=SERVICE_SCHEMAS[SERVICE_PERMIT],
    )
    async_register_admin_service(
        hass, DOMAIN, SERVICE_REMOVE, _remove, schema=SERVICE_SCHEMAS[IEEE_SERVICE]
    )
    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_SET_ZIGBEE_CLUSTER_ATTRIBUTE,
        _set_zigbee_cluster_attributes,
        schema=SERVICE_SCHEMAS[SERVICE_SET_ZIGBEE_CLUSTER_ATTRIBUTE],
    )
    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_ISSUE_ZIGBEE_CLUSTER_COMMAND,
        _issue_zigbee_cluster_command,
        schema=SERVICE_SCHEMAS[SERVICE_ISSUE_ZIGBEE_CLUSTER_COMMAND],
    )
    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_ISSUE_ZIGBEE_GROUP_COMMAND,
        _issue_zigbee_group_command,
        schema=SERVICE_SCHEMAS[SERVICE_ISSUE_ZIGBEE_GROUP_COMMAND],
    )
    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_WARNING_DEVICE_SQUAWK,
        _warning_device_squawk,
        schema=SERVICE_SCHEMAS[SERVICE_WARNING_DEVICE_SQUAWK],
    )
    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_WARNING_DEVICE_WARN,
        _warning_device_warn,
        schema=SERVICE_SCHEMAS[SERVICE_WARNING_DEVICE_WARN],
    )
