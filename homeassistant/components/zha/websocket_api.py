"""Web socket API for Zigbee Home Automation devices."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any, Literal, NamedTuple, cast

import voluptuous as vol
import zigpy.backups
from zigpy.config import CONF_DEVICE
from zigpy.config.validators import cv_boolean
from zigpy.types.named import EUI64, KeyData
from zigpy.zcl.clusters.security import IasAce
import zigpy.zdo.types as zdo_types

from homeassistant.components import websocket_api
from homeassistant.const import ATTR_COMMAND, ATTR_ID, ATTR_NAME
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import entity_registry as er
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.service import async_register_admin_service
from homeassistant.helpers.typing import VolDictType, VolSchemaType

from .api import (
    async_change_channel,
    async_get_active_network_settings,
    async_get_radio_type,
)
from .core.const import (
    ATTR_ARGS,
    ATTR_ATTRIBUTE,
    ATTR_CLUSTER_ID,
    ATTR_CLUSTER_TYPE,
    ATTR_COMMAND_TYPE,
    ATTR_ENDPOINT_ID,
    ATTR_IEEE,
    ATTR_LEVEL,
    ATTR_MANUFACTURER,
    ATTR_MEMBERS,
    ATTR_PARAMS,
    ATTR_TYPE,
    ATTR_VALUE,
    ATTR_WARNING_DEVICE_DURATION,
    ATTR_WARNING_DEVICE_MODE,
    ATTR_WARNING_DEVICE_STROBE,
    ATTR_WARNING_DEVICE_STROBE_DUTY_CYCLE,
    ATTR_WARNING_DEVICE_STROBE_INTENSITY,
    BINDINGS,
    CLUSTER_COMMAND_SERVER,
    CLUSTER_COMMANDS_CLIENT,
    CLUSTER_COMMANDS_SERVER,
    CLUSTER_HANDLER_IAS_WD,
    CLUSTER_TYPE_IN,
    CLUSTER_TYPE_OUT,
    CUSTOM_CONFIGURATION,
    DOMAIN,
    EZSP_OVERWRITE_EUI64,
    GROUP_ID,
    GROUP_IDS,
    GROUP_NAME,
    MFG_CLUSTER_ID_START,
    WARNING_DEVICE_MODE_EMERGENCY,
    WARNING_DEVICE_SOUND_HIGH,
    WARNING_DEVICE_SQUAWK_MODE_ARMED,
    WARNING_DEVICE_STROBE_HIGH,
    WARNING_DEVICE_STROBE_YES,
    ZHA_ALARM_OPTIONS,
    ZHA_CLUSTER_HANDLER_MSG,
    ZHA_CONFIG_SCHEMAS,
)
from .core.gateway import EntityReference
from .core.group import GroupMember
from .core.helpers import (
    async_cluster_exists,
    async_is_bindable_target,
    cluster_command_schema_to_vol_schema,
    convert_install_code,
    get_matched_clusters,
    get_zha_gateway,
    qr_to_install_code,
)

if TYPE_CHECKING:
    from homeassistant.components.websocket_api.connection import ActiveConnection

    from .core.device import ZHADevice
    from .core.gateway import ZHAGateway

_LOGGER = logging.getLogger(__name__)

TYPE = "type"
CLIENT = "client"
ID = "id"
RESPONSE = "response"
DEVICE_INFO = "device_info"

ATTR_DURATION = "duration"
ATTR_GROUP = "group"
ATTR_IEEE_ADDRESS = "ieee_address"
ATTR_INSTALL_CODE = "install_code"
ATTR_NEW_CHANNEL = "new_channel"
ATTR_SOURCE_IEEE = "source_ieee"
ATTR_TARGET_IEEE = "target_ieee"
ATTR_QR_CODE = "qr_code"

SERVICE_PERMIT = "permit"
SERVICE_REMOVE = "remove"
SERVICE_SET_ZIGBEE_CLUSTER_ATTRIBUTE = "set_zigbee_cluster_attribute"
SERVICE_ISSUE_ZIGBEE_CLUSTER_COMMAND = "issue_zigbee_cluster_command"
SERVICE_ISSUE_ZIGBEE_GROUP_COMMAND = "issue_zigbee_group_command"
SERVICE_DIRECT_ZIGBEE_BIND = "issue_direct_zigbee_bind"
SERVICE_DIRECT_ZIGBEE_UNBIND = "issue_direct_zigbee_unbind"
SERVICE_WARNING_DEVICE_SQUAWK = "warning_device_squawk"
SERVICE_WARNING_DEVICE_WARN = "warning_device_warn"
SERVICE_ZIGBEE_BIND = "service_zigbee_bind"
IEEE_SERVICE = "ieee_based_service"

IEEE_SCHEMA = vol.All(cv.string, EUI64.convert)


def _ensure_list_if_present[_T](value: _T | None) -> list[_T] | list[Any] | None:
    """Wrap value in list if it is provided and not one."""
    if value is None:
        return None
    return cast("list[_T]", value) if isinstance(value, list) else [value]


SERVICE_PERMIT_PARAMS: VolDictType = {
    vol.Optional(ATTR_IEEE): IEEE_SCHEMA,
    vol.Optional(ATTR_DURATION, default=60): vol.All(
        vol.Coerce(int), vol.Range(0, 254)
    ),
    vol.Inclusive(ATTR_SOURCE_IEEE, "install_code"): IEEE_SCHEMA,
    vol.Inclusive(ATTR_INSTALL_CODE, "install_code"): vol.All(
        cv.string, convert_install_code
    ),
    vol.Exclusive(ATTR_QR_CODE, "install_code"): vol.All(cv.string, qr_to_install_code),
}

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
                ATTR_WARNING_DEVICE_MODE, default=WARNING_DEVICE_SQUAWK_MODE_ARMED
            ): cv.positive_int,
            vol.Optional(
                ATTR_WARNING_DEVICE_STROBE, default=WARNING_DEVICE_STROBE_YES
            ): cv.positive_int,
            vol.Optional(
                ATTR_LEVEL, default=WARNING_DEVICE_SOUND_HIGH
            ): cv.positive_int,
        }
    ),
    SERVICE_WARNING_DEVICE_WARN: vol.Schema(
        {
            vol.Required(ATTR_IEEE): IEEE_SCHEMA,
            vol.Optional(
                ATTR_WARNING_DEVICE_MODE, default=WARNING_DEVICE_MODE_EMERGENCY
            ): cv.positive_int,
            vol.Optional(
                ATTR_WARNING_DEVICE_STROBE, default=WARNING_DEVICE_STROBE_YES
            ): cv.positive_int,
            vol.Optional(
                ATTR_LEVEL, default=WARNING_DEVICE_SOUND_HIGH
            ): cv.positive_int,
            vol.Optional(ATTR_WARNING_DEVICE_DURATION, default=5): cv.positive_int,
            vol.Optional(
                ATTR_WARNING_DEVICE_STROBE_DUTY_CYCLE, default=0x00
            ): cv.positive_int,
            vol.Optional(
                ATTR_WARNING_DEVICE_STROBE_INTENSITY, default=WARNING_DEVICE_STROBE_HIGH
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


class ClusterBinding(NamedTuple):
    """Describes a cluster binding."""

    name: str
    type: str
    id: int
    endpoint_id: int


def _cv_group_member(value: dict[str, Any]) -> GroupMember:
    """Transform a group member."""
    return GroupMember(
        ieee=value[ATTR_IEEE],
        endpoint_id=value[ATTR_ENDPOINT_ID],
    )


def _cv_cluster_binding(value: dict[str, Any]) -> ClusterBinding:
    """Transform a cluster binding."""
    return ClusterBinding(
        name=value[ATTR_NAME],
        type=value[ATTR_TYPE],
        id=value[ATTR_ID],
        endpoint_id=value[ATTR_ENDPOINT_ID],
    )


def _cv_zigpy_network_backup(value: dict[str, Any]) -> zigpy.backups.NetworkBackup:
    """Transform a zigpy network backup."""

    try:
        return zigpy.backups.NetworkBackup.from_dict(value)
    except ValueError as err:
        raise vol.Invalid(str(err)) from err


GROUP_MEMBER_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Required(ATTR_IEEE): IEEE_SCHEMA,
            vol.Required(ATTR_ENDPOINT_ID): vol.Coerce(int),
        }
    ),
    _cv_group_member,
)


CLUSTER_BINDING_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Required(ATTR_NAME): cv.string,
            vol.Required(ATTR_TYPE): cv.string,
            vol.Required(ATTR_ID): vol.Coerce(int),
            vol.Required(ATTR_ENDPOINT_ID): vol.Coerce(int),
        }
    ),
    _cv_cluster_binding,
)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "zha/devices/permit",
        **SERVICE_PERMIT_PARAMS,
    }
)
@websocket_api.async_response
async def websocket_permit_devices(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Permit ZHA zigbee devices."""
    zha_gateway = get_zha_gateway(hass)
    duration: int = msg[ATTR_DURATION]
    ieee: EUI64 | None = msg.get(ATTR_IEEE)

    async def forward_messages(data):
        """Forward events to websocket."""
        connection.send_message(websocket_api.event_message(msg["id"], data))

    remove_dispatcher_function = async_dispatcher_connect(
        hass, "zha_gateway_message", forward_messages
    )

    @callback
    def async_cleanup() -> None:
        """Remove signal listener and turn off debug mode."""
        zha_gateway.async_disable_debug_mode()
        remove_dispatcher_function()

    connection.subscriptions[msg["id"]] = async_cleanup
    zha_gateway.async_enable_debug_mode()
    src_ieee: EUI64
    link_key: KeyData
    if ATTR_SOURCE_IEEE in msg:
        src_ieee = msg[ATTR_SOURCE_IEEE]
        link_key = msg[ATTR_INSTALL_CODE]
        _LOGGER.debug("Allowing join for %s device with link key", src_ieee)
        await zha_gateway.application_controller.permit_with_link_key(
            time_s=duration, node=src_ieee, link_key=link_key
        )
    elif ATTR_QR_CODE in msg:
        src_ieee, link_key = msg[ATTR_QR_CODE]
        _LOGGER.debug("Allowing join for %s device with link key", src_ieee)
        await zha_gateway.application_controller.permit_with_link_key(
            time_s=duration, node=src_ieee, link_key=link_key
        )
    else:
        await zha_gateway.application_controller.permit(time_s=duration, node=ieee)
    connection.send_result(msg[ID])


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required(TYPE): "zha/devices"})
@websocket_api.async_response
async def websocket_get_devices(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Get ZHA devices."""
    zha_gateway = get_zha_gateway(hass)
    devices = [device.zha_device_info for device in zha_gateway.devices.values()]
    connection.send_result(msg[ID], devices)


@callback
def _get_entity_name(
    zha_gateway: ZHAGateway, entity_ref: EntityReference
) -> str | None:
    entity_registry = er.async_get(zha_gateway.hass)
    entry = entity_registry.async_get(entity_ref.reference_id)
    return entry.name if entry else None


@callback
def _get_entity_original_name(
    zha_gateway: ZHAGateway, entity_ref: EntityReference
) -> str | None:
    entity_registry = er.async_get(zha_gateway.hass)
    entry = entity_registry.async_get(entity_ref.reference_id)
    return entry.original_name if entry else None


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required(TYPE): "zha/devices/groupable"})
@websocket_api.async_response
async def websocket_get_groupable_devices(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Get ZHA devices that can be grouped."""
    zha_gateway = get_zha_gateway(hass)

    devices = [device for device in zha_gateway.devices.values() if device.is_groupable]
    groupable_devices: list[dict[str, Any]] = []

    for device in devices:
        entity_refs = zha_gateway.device_registry[device.ieee]
        groupable_devices.extend(
            {
                "endpoint_id": ep_id,
                "entities": [
                    {
                        "name": _get_entity_name(zha_gateway, entity_ref),
                        "original_name": _get_entity_original_name(
                            zha_gateway, entity_ref
                        ),
                    }
                    for entity_ref in entity_refs
                    if list(entity_ref.cluster_handlers.values())[
                        0
                    ].cluster.endpoint.endpoint_id
                    == ep_id
                ],
                "device": device.zha_device_info,
            }
            for ep_id in device.async_get_groupable_endpoints()
        )

    connection.send_result(msg[ID], groupable_devices)


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required(TYPE): "zha/groups"})
@websocket_api.async_response
async def websocket_get_groups(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Get ZHA groups."""
    zha_gateway = get_zha_gateway(hass)
    groups = [group.group_info for group in zha_gateway.groups.values()]
    connection.send_result(msg[ID], groups)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zha/device",
        vol.Required(ATTR_IEEE): IEEE_SCHEMA,
    }
)
@websocket_api.async_response
async def websocket_get_device(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Get ZHA devices."""
    zha_gateway = get_zha_gateway(hass)
    ieee: EUI64 = msg[ATTR_IEEE]

    if not (zha_device := zha_gateway.devices.get(ieee)):
        connection.send_message(
            websocket_api.error_message(
                msg[ID], websocket_api.ERR_NOT_FOUND, "ZHA Device not found"
            )
        )
        return

    device_info = zha_device.zha_device_info
    connection.send_result(msg[ID], device_info)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zha/group",
        vol.Required(GROUP_ID): cv.positive_int,
    }
)
@websocket_api.async_response
async def websocket_get_group(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Get ZHA group."""
    zha_gateway = get_zha_gateway(hass)
    group_id: int = msg[GROUP_ID]

    if not (zha_group := zha_gateway.groups.get(group_id)):
        connection.send_message(
            websocket_api.error_message(
                msg[ID], websocket_api.ERR_NOT_FOUND, "ZHA Group not found"
            )
        )
        return

    group_info = zha_group.group_info
    connection.send_result(msg[ID], group_info)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zha/group/add",
        vol.Required(GROUP_NAME): cv.string,
        vol.Optional(GROUP_ID): cv.positive_int,
        vol.Optional(ATTR_MEMBERS): vol.All(cv.ensure_list, [GROUP_MEMBER_SCHEMA]),
    }
)
@websocket_api.async_response
async def websocket_add_group(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Add a new ZHA group."""
    zha_gateway = get_zha_gateway(hass)
    group_name: str = msg[GROUP_NAME]
    group_id: int | None = msg.get(GROUP_ID)
    members: list[GroupMember] | None = msg.get(ATTR_MEMBERS)
    group = await zha_gateway.async_create_zigpy_group(group_name, members, group_id)
    assert group
    connection.send_result(msg[ID], group.group_info)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zha/group/remove",
        vol.Required(GROUP_IDS): vol.All(cv.ensure_list, [cv.positive_int]),
    }
)
@websocket_api.async_response
async def websocket_remove_groups(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Remove the specified ZHA groups."""
    zha_gateway = get_zha_gateway(hass)
    group_ids: list[int] = msg[GROUP_IDS]

    if len(group_ids) > 1:
        tasks = [
            zha_gateway.async_remove_zigpy_group(group_id) for group_id in group_ids
        ]
        await asyncio.gather(*tasks)
    else:
        await zha_gateway.async_remove_zigpy_group(group_ids[0])
    ret_groups = [group.group_info for group in zha_gateway.groups.values()]
    connection.send_result(msg[ID], ret_groups)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zha/group/members/add",
        vol.Required(GROUP_ID): cv.positive_int,
        vol.Required(ATTR_MEMBERS): vol.All(cv.ensure_list, [GROUP_MEMBER_SCHEMA]),
    }
)
@websocket_api.async_response
async def websocket_add_group_members(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Add members to a ZHA group."""
    zha_gateway = get_zha_gateway(hass)
    group_id: int = msg[GROUP_ID]
    members: list[GroupMember] = msg[ATTR_MEMBERS]

    if not (zha_group := zha_gateway.groups.get(group_id)):
        connection.send_message(
            websocket_api.error_message(
                msg[ID], websocket_api.ERR_NOT_FOUND, "ZHA Group not found"
            )
        )
        return

    await zha_group.async_add_members(members)
    ret_group = zha_group.group_info
    connection.send_result(msg[ID], ret_group)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zha/group/members/remove",
        vol.Required(GROUP_ID): cv.positive_int,
        vol.Required(ATTR_MEMBERS): vol.All(cv.ensure_list, [GROUP_MEMBER_SCHEMA]),
    }
)
@websocket_api.async_response
async def websocket_remove_group_members(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Remove members from a ZHA group."""
    zha_gateway = get_zha_gateway(hass)
    group_id: int = msg[GROUP_ID]
    members: list[GroupMember] = msg[ATTR_MEMBERS]

    if not (zha_group := zha_gateway.groups.get(group_id)):
        connection.send_message(
            websocket_api.error_message(
                msg[ID], websocket_api.ERR_NOT_FOUND, "ZHA Group not found"
            )
        )
        return

    await zha_group.async_remove_members(members)
    ret_group = zha_group.group_info
    connection.send_result(msg[ID], ret_group)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zha/devices/reconfigure",
        vol.Required(ATTR_IEEE): IEEE_SCHEMA,
    }
)
@websocket_api.async_response
async def websocket_reconfigure_node(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Reconfigure a ZHA nodes entities by its ieee address."""
    zha_gateway = get_zha_gateway(hass)
    ieee: EUI64 = msg[ATTR_IEEE]
    device: ZHADevice | None = zha_gateway.get_device(ieee)

    async def forward_messages(data):
        """Forward events to websocket."""
        connection.send_message(websocket_api.event_message(msg["id"], data))

    remove_dispatcher_function = async_dispatcher_connect(
        hass, ZHA_CLUSTER_HANDLER_MSG, forward_messages
    )

    @callback
    def async_cleanup() -> None:
        """Remove signal listener."""
        remove_dispatcher_function()

    connection.subscriptions[msg["id"]] = async_cleanup

    _LOGGER.debug("Reconfiguring node with ieee_address: %s", ieee)
    assert device
    hass.async_create_task(device.async_configure())


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zha/topology/update",
    }
)
@websocket_api.async_response
async def websocket_update_topology(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Update the ZHA network topology."""
    zha_gateway = get_zha_gateway(hass)
    hass.async_create_task(zha_gateway.application_controller.topology.scan())


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zha/devices/clusters",
        vol.Required(ATTR_IEEE): IEEE_SCHEMA,
    }
)
@websocket_api.async_response
async def websocket_device_clusters(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Return a list of device clusters."""
    zha_gateway = get_zha_gateway(hass)
    ieee: EUI64 = msg[ATTR_IEEE]
    zha_device = zha_gateway.get_device(ieee)
    response_clusters = []
    if zha_device is not None:
        clusters_by_endpoint = zha_device.async_get_clusters()
        for ep_id, clusters in clusters_by_endpoint.items():
            for c_id, cluster in clusters[CLUSTER_TYPE_IN].items():
                response_clusters.append(
                    {
                        TYPE: CLUSTER_TYPE_IN,
                        ID: c_id,
                        ATTR_NAME: cluster.__class__.__name__,
                        "endpoint_id": ep_id,
                    }
                )
            for c_id, cluster in clusters[CLUSTER_TYPE_OUT].items():
                response_clusters.append(
                    {
                        TYPE: CLUSTER_TYPE_OUT,
                        ID: c_id,
                        ATTR_NAME: cluster.__class__.__name__,
                        "endpoint_id": ep_id,
                    }
                )

    connection.send_result(msg[ID], response_clusters)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zha/devices/clusters/attributes",
        vol.Required(ATTR_IEEE): IEEE_SCHEMA,
        vol.Required(ATTR_ENDPOINT_ID): int,
        vol.Required(ATTR_CLUSTER_ID): int,
        vol.Required(ATTR_CLUSTER_TYPE): str,
    }
)
@websocket_api.async_response
async def websocket_device_cluster_attributes(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Return a list of cluster attributes."""
    zha_gateway = get_zha_gateway(hass)
    ieee: EUI64 = msg[ATTR_IEEE]
    endpoint_id: int = msg[ATTR_ENDPOINT_ID]
    cluster_id: int = msg[ATTR_CLUSTER_ID]
    cluster_type: str = msg[ATTR_CLUSTER_TYPE]
    cluster_attributes: list[dict[str, Any]] = []
    zha_device = zha_gateway.get_device(ieee)
    attributes = None
    if zha_device is not None:
        attributes = zha_device.async_get_cluster_attributes(
            endpoint_id, cluster_id, cluster_type
        )
        if attributes is not None:
            for attr_id, attr in attributes.items():
                cluster_attributes.append({ID: attr_id, ATTR_NAME: attr.name})
    _LOGGER.debug(
        "Requested attributes for: %s: %s, %s: '%s', %s: %s, %s: %s",
        ATTR_CLUSTER_ID,
        cluster_id,
        ATTR_CLUSTER_TYPE,
        cluster_type,
        ATTR_ENDPOINT_ID,
        endpoint_id,
        RESPONSE,
        cluster_attributes,
    )

    connection.send_result(msg[ID], cluster_attributes)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zha/devices/clusters/commands",
        vol.Required(ATTR_IEEE): IEEE_SCHEMA,
        vol.Required(ATTR_ENDPOINT_ID): int,
        vol.Required(ATTR_CLUSTER_ID): int,
        vol.Required(ATTR_CLUSTER_TYPE): str,
    }
)
@websocket_api.async_response
async def websocket_device_cluster_commands(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Return a list of cluster commands."""
    import voluptuous_serialize  # pylint: disable=import-outside-toplevel

    zha_gateway = get_zha_gateway(hass)
    ieee: EUI64 = msg[ATTR_IEEE]
    endpoint_id: int = msg[ATTR_ENDPOINT_ID]
    cluster_id: int = msg[ATTR_CLUSTER_ID]
    cluster_type: str = msg[ATTR_CLUSTER_TYPE]
    zha_device = zha_gateway.get_device(ieee)
    cluster_commands: list[dict[str, Any]] = []
    commands = None
    if zha_device is not None:
        commands = zha_device.async_get_cluster_commands(
            endpoint_id, cluster_id, cluster_type
        )

        if commands is not None:
            for cmd_id, cmd in commands[CLUSTER_COMMANDS_CLIENT].items():
                cluster_commands.append(
                    {
                        TYPE: CLIENT,
                        ID: cmd_id,
                        ATTR_NAME: cmd.name,
                        "schema": voluptuous_serialize.convert(
                            cluster_command_schema_to_vol_schema(cmd.schema),
                            custom_serializer=cv.custom_serializer,
                        ),
                    }
                )
            for cmd_id, cmd in commands[CLUSTER_COMMANDS_SERVER].items():
                cluster_commands.append(
                    {
                        TYPE: CLUSTER_COMMAND_SERVER,
                        ID: cmd_id,
                        ATTR_NAME: cmd.name,
                        "schema": voluptuous_serialize.convert(
                            cluster_command_schema_to_vol_schema(cmd.schema),
                            custom_serializer=cv.custom_serializer,
                        ),
                    }
                )
    _LOGGER.debug(
        "Requested commands for: %s: %s, %s: '%s', %s: %s, %s: %s",
        ATTR_CLUSTER_ID,
        cluster_id,
        ATTR_CLUSTER_TYPE,
        cluster_type,
        ATTR_ENDPOINT_ID,
        endpoint_id,
        RESPONSE,
        cluster_commands,
    )

    connection.send_result(msg[ID], cluster_commands)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zha/devices/clusters/attributes/value",
        vol.Required(ATTR_IEEE): IEEE_SCHEMA,
        vol.Required(ATTR_ENDPOINT_ID): int,
        vol.Required(ATTR_CLUSTER_ID): int,
        vol.Required(ATTR_CLUSTER_TYPE): str,
        vol.Required(ATTR_ATTRIBUTE): int,
        vol.Optional(ATTR_MANUFACTURER): cv.positive_int,
    }
)
@websocket_api.async_response
async def websocket_read_zigbee_cluster_attributes(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Read zigbee attribute for cluster on ZHA entity."""
    zha_gateway = get_zha_gateway(hass)
    ieee: EUI64 = msg[ATTR_IEEE]
    endpoint_id: int = msg[ATTR_ENDPOINT_ID]
    cluster_id: int = msg[ATTR_CLUSTER_ID]
    cluster_type: str = msg[ATTR_CLUSTER_TYPE]
    attribute: int = msg[ATTR_ATTRIBUTE]
    manufacturer: int | None = msg.get(ATTR_MANUFACTURER)
    zha_device = zha_gateway.get_device(ieee)
    success = {}
    failure = {}
    if zha_device is not None:
        cluster = zha_device.async_get_cluster(
            endpoint_id, cluster_id, cluster_type=cluster_type
        )
        success, failure = await cluster.read_attributes(
            [attribute], allow_cache=False, only_cache=False, manufacturer=manufacturer
        )
    _LOGGER.debug(
        (
            "Read attribute for: %s: [%s] %s: [%s] %s: [%s] %s: [%s] %s: [%s] %s: [%s]"
            " %s: [%s],"
        ),
        ATTR_CLUSTER_ID,
        cluster_id,
        ATTR_CLUSTER_TYPE,
        cluster_type,
        ATTR_ENDPOINT_ID,
        endpoint_id,
        ATTR_ATTRIBUTE,
        attribute,
        ATTR_MANUFACTURER,
        manufacturer,
        RESPONSE,
        str(success.get(attribute)),
        "failure",
        failure,
    )
    connection.send_result(msg[ID], str(success.get(attribute)))


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zha/devices/bindable",
        vol.Required(ATTR_IEEE): IEEE_SCHEMA,
    }
)
@websocket_api.async_response
async def websocket_get_bindable_devices(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Directly bind devices."""
    zha_gateway = get_zha_gateway(hass)
    source_ieee: EUI64 = msg[ATTR_IEEE]
    source_device = zha_gateway.get_device(source_ieee)

    devices = [
        device.zha_device_info
        for device in zha_gateway.devices.values()
        if async_is_bindable_target(source_device, device)
    ]

    _LOGGER.debug(
        "Get bindable devices: %s: [%s], %s: [%s]",
        ATTR_SOURCE_IEEE,
        source_ieee,
        "bindable devices",
        devices,
    )

    connection.send_message(websocket_api.result_message(msg[ID], devices))


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zha/devices/bind",
        vol.Required(ATTR_SOURCE_IEEE): IEEE_SCHEMA,
        vol.Required(ATTR_TARGET_IEEE): IEEE_SCHEMA,
    }
)
@websocket_api.async_response
async def websocket_bind_devices(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Directly bind devices."""
    zha_gateway = get_zha_gateway(hass)
    source_ieee: EUI64 = msg[ATTR_SOURCE_IEEE]
    target_ieee: EUI64 = msg[ATTR_TARGET_IEEE]
    await async_binding_operation(
        zha_gateway, source_ieee, target_ieee, zdo_types.ZDOCmd.Bind_req
    )
    _LOGGER.info(
        "Devices bound: %s: [%s] %s: [%s]",
        ATTR_SOURCE_IEEE,
        source_ieee,
        ATTR_TARGET_IEEE,
        target_ieee,
    )
    connection.send_result(msg[ID])


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zha/devices/unbind",
        vol.Required(ATTR_SOURCE_IEEE): IEEE_SCHEMA,
        vol.Required(ATTR_TARGET_IEEE): IEEE_SCHEMA,
    }
)
@websocket_api.async_response
async def websocket_unbind_devices(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Remove a direct binding between devices."""
    zha_gateway = get_zha_gateway(hass)
    source_ieee: EUI64 = msg[ATTR_SOURCE_IEEE]
    target_ieee: EUI64 = msg[ATTR_TARGET_IEEE]
    await async_binding_operation(
        zha_gateway, source_ieee, target_ieee, zdo_types.ZDOCmd.Unbind_req
    )
    _LOGGER.info(
        "Devices un-bound: %s: [%s] %s: [%s]",
        ATTR_SOURCE_IEEE,
        source_ieee,
        ATTR_TARGET_IEEE,
        target_ieee,
    )
    connection.send_result(msg[ID])


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zha/groups/bind",
        vol.Required(ATTR_SOURCE_IEEE): IEEE_SCHEMA,
        vol.Required(GROUP_ID): cv.positive_int,
        vol.Required(BINDINGS): vol.All(cv.ensure_list, [CLUSTER_BINDING_SCHEMA]),
    }
)
@websocket_api.async_response
async def websocket_bind_group(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Directly bind a device to a group."""
    zha_gateway = get_zha_gateway(hass)
    source_ieee: EUI64 = msg[ATTR_SOURCE_IEEE]
    group_id: int = msg[GROUP_ID]
    bindings: list[ClusterBinding] = msg[BINDINGS]
    source_device = zha_gateway.get_device(source_ieee)
    assert source_device
    await source_device.async_bind_to_group(group_id, bindings)
    connection.send_result(msg[ID])


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zha/groups/unbind",
        vol.Required(ATTR_SOURCE_IEEE): IEEE_SCHEMA,
        vol.Required(GROUP_ID): cv.positive_int,
        vol.Required(BINDINGS): vol.All(cv.ensure_list, [CLUSTER_BINDING_SCHEMA]),
    }
)
@websocket_api.async_response
async def websocket_unbind_group(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Unbind a device from a group."""
    zha_gateway = get_zha_gateway(hass)
    source_ieee: EUI64 = msg[ATTR_SOURCE_IEEE]
    group_id: int = msg[GROUP_ID]
    bindings: list[ClusterBinding] = msg[BINDINGS]
    source_device = zha_gateway.get_device(source_ieee)
    assert source_device
    await source_device.async_unbind_from_group(group_id, bindings)
    connection.send_result(msg[ID])


async def async_binding_operation(
    zha_gateway: ZHAGateway,
    source_ieee: EUI64,
    target_ieee: EUI64,
    operation: zdo_types.ZDOCmd,
) -> None:
    """Create or remove a direct zigbee binding between 2 devices."""

    source_device = zha_gateway.get_device(source_ieee)
    target_device = zha_gateway.get_device(target_ieee)

    assert source_device
    assert target_device
    clusters_to_bind = await get_matched_clusters(source_device, target_device)

    zdo = source_device.device.zdo
    bind_tasks = []
    for binding_pair in clusters_to_bind:
        op_msg = "cluster: %s %s --> [%s]"
        op_params = (
            binding_pair.source_cluster.cluster_id,
            operation.name,
            target_ieee,
        )
        zdo.debug(f"processing {op_msg}", *op_params)

        bind_tasks.append(
            (
                zdo.request(
                    operation,
                    source_device.ieee,
                    binding_pair.source_cluster.endpoint.endpoint_id,
                    binding_pair.source_cluster.cluster_id,
                    binding_pair.destination_address,
                ),
                op_msg,
                op_params,
            )
        )
    res = await asyncio.gather(*(t[0] for t in bind_tasks), return_exceptions=True)
    for outcome, log_msg in zip(res, bind_tasks, strict=False):
        if isinstance(outcome, Exception):
            fmt = f"{log_msg[1]} failed: %s"
        else:
            fmt = f"{log_msg[1]} completed: %s"
        zdo.debug(fmt, *(log_msg[2] + (outcome,)))


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required(TYPE): "zha/configuration"})
@websocket_api.async_response
async def websocket_get_configuration(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Get ZHA configuration."""
    zha_gateway = get_zha_gateway(hass)
    import voluptuous_serialize  # pylint: disable=import-outside-toplevel

    def custom_serializer(schema: Any) -> Any:
        """Serialize additional types for voluptuous_serialize."""
        if schema is cv_boolean:
            return {"type": "bool"}
        if schema is vol.Schema:
            return voluptuous_serialize.convert(
                schema, custom_serializer=custom_serializer
            )

        return cv.custom_serializer(schema)

    data: dict[str, dict[str, Any]] = {"schemas": {}, "data": {}}
    for section, schema in ZHA_CONFIG_SCHEMAS.items():
        if section == ZHA_ALARM_OPTIONS and not async_cluster_exists(
            hass, IasAce.cluster_id
        ):
            continue
        data["schemas"][section] = voluptuous_serialize.convert(
            schema, custom_serializer=custom_serializer
        )
        data["data"][section] = zha_gateway.config_entry.options.get(
            CUSTOM_CONFIGURATION, {}
        ).get(section, {})

        # send default values for unconfigured options
        for entry in data["schemas"][section]:
            if data["data"][section].get(entry["name"]) is None:
                data["data"][section][entry["name"]] = entry["default"]

    connection.send_result(msg[ID], data)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zha/configuration/update",
        vol.Required("data"): ZHA_CONFIG_SCHEMAS,
    }
)
@websocket_api.async_response
async def websocket_update_zha_configuration(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Update the ZHA configuration."""
    zha_gateway = get_zha_gateway(hass)
    options = zha_gateway.config_entry.options
    data_to_save = {**options, CUSTOM_CONFIGURATION: msg["data"]}

    for section, schema in ZHA_CONFIG_SCHEMAS.items():
        for entry in schema.schema:
            # remove options that match defaults
            if (
                data_to_save[CUSTOM_CONFIGURATION].get(section, {}).get(entry)
                == entry.default()
            ):
                data_to_save[CUSTOM_CONFIGURATION][section].pop(entry)
            # remove entire section block if empty
            if (
                not data_to_save[CUSTOM_CONFIGURATION].get(section)
                and section in data_to_save[CUSTOM_CONFIGURATION]
            ):
                data_to_save[CUSTOM_CONFIGURATION].pop(section)

    # remove entire custom_configuration block if empty
    if (
        not data_to_save.get(CUSTOM_CONFIGURATION)
        and CUSTOM_CONFIGURATION in data_to_save
    ):
        data_to_save.pop(CUSTOM_CONFIGURATION)

    _LOGGER.info(
        "Updating ZHA custom configuration options from %s to %s",
        options,
        data_to_save,
    )

    hass.config_entries.async_update_entry(
        zha_gateway.config_entry, options=data_to_save
    )
    status = await hass.config_entries.async_reload(zha_gateway.config_entry.entry_id)
    connection.send_result(msg[ID], status)


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required(TYPE): "zha/network/settings"})
@websocket_api.async_response
async def websocket_get_network_settings(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Get ZHA network settings."""
    backup = async_get_active_network_settings(hass)
    zha_gateway = get_zha_gateway(hass)
    connection.send_result(
        msg[ID],
        {
            "radio_type": async_get_radio_type(hass, zha_gateway.config_entry).name,
            "device": zha_gateway.application_controller.config[CONF_DEVICE],
            "settings": backup.as_dict(),
        },
    )


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required(TYPE): "zha/network/backups/list"})
@websocket_api.async_response
async def websocket_list_network_backups(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Get ZHA network settings."""
    zha_gateway = get_zha_gateway(hass)
    application_controller = zha_gateway.application_controller

    # Serialize known backups
    connection.send_result(
        msg[ID], [backup.as_dict() for backup in application_controller.backups]
    )


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required(TYPE): "zha/network/backups/create"})
@websocket_api.async_response
async def websocket_create_network_backup(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Create a ZHA network backup."""
    zha_gateway = get_zha_gateway(hass)
    application_controller = zha_gateway.application_controller

    # This can take 5-30s
    backup = await application_controller.backups.create_backup(load_devices=True)
    connection.send_result(
        msg[ID],
        {
            "backup": backup.as_dict(),
            "is_complete": backup.is_complete(),
        },
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zha/network/backups/restore",
        vol.Required("backup"): _cv_zigpy_network_backup,
        vol.Optional("ezsp_force_write_eui64", default=False): cv.boolean,
    }
)
@websocket_api.async_response
async def websocket_restore_network_backup(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Restore a ZHA network backup."""
    zha_gateway = get_zha_gateway(hass)
    application_controller = zha_gateway.application_controller
    backup = msg["backup"]

    if msg["ezsp_force_write_eui64"]:
        backup.network_info.stack_specific.setdefault("ezsp", {})[
            EZSP_OVERWRITE_EUI64
        ] = True

    # This can take 30-40s
    try:
        await application_controller.backups.restore_backup(backup)
    except ValueError as err:
        connection.send_error(msg[ID], websocket_api.ERR_INVALID_FORMAT, str(err))
    else:
        connection.send_result(msg[ID])


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zha/network/change_channel",
        vol.Required(ATTR_NEW_CHANNEL): vol.Any("auto", vol.Range(11, 26)),
    }
)
@websocket_api.async_response
async def websocket_change_channel(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Migrate the Zigbee network to a new channel."""
    new_channel = cast(Literal["auto"] | int, msg[ATTR_NEW_CHANNEL])
    await async_change_channel(hass, new_channel=new_channel)
    connection.send_result(msg[ID])


@callback
def async_load_api(hass: HomeAssistant) -> None:
    """Set up the web socket API."""
    zha_gateway = get_zha_gateway(hass)
    application_controller = zha_gateway.application_controller

    async def permit(service: ServiceCall) -> None:
        """Allow devices to join this network."""
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

    async_register_admin_service(
        hass, DOMAIN, SERVICE_PERMIT, permit, schema=SERVICE_SCHEMAS[SERVICE_PERMIT]
    )

    async def remove(service: ServiceCall) -> None:
        """Remove a node from the network."""
        zha_gateway = get_zha_gateway(hass)
        ieee: EUI64 = service.data[ATTR_IEEE]
        zha_device: ZHADevice | None = zha_gateway.get_device(ieee)
        if zha_device is not None and zha_device.is_active_coordinator:
            _LOGGER.info("Removing the coordinator (%s) is not allowed", ieee)
            return
        _LOGGER.info("Removing node %s", ieee)
        await application_controller.remove(ieee)

    async_register_admin_service(
        hass, DOMAIN, SERVICE_REMOVE, remove, schema=SERVICE_SCHEMAS[IEEE_SERVICE]
    )

    async def set_zigbee_cluster_attributes(service: ServiceCall) -> None:
        """Set zigbee attribute for cluster on zha entity."""
        ieee: EUI64 = service.data[ATTR_IEEE]
        endpoint_id: int = service.data[ATTR_ENDPOINT_ID]
        cluster_id: int = service.data[ATTR_CLUSTER_ID]
        cluster_type: str = service.data[ATTR_CLUSTER_TYPE]
        attribute: int | str = service.data[ATTR_ATTRIBUTE]
        value: int | bool | str = service.data[ATTR_VALUE]
        manufacturer: int | None = service.data.get(ATTR_MANUFACTURER)
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

    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_SET_ZIGBEE_CLUSTER_ATTRIBUTE,
        set_zigbee_cluster_attributes,
        schema=SERVICE_SCHEMAS[SERVICE_SET_ZIGBEE_CLUSTER_ATTRIBUTE],
    )

    async def issue_zigbee_cluster_command(service: ServiceCall) -> None:
        """Issue command on zigbee cluster on ZHA entity."""
        ieee: EUI64 = service.data[ATTR_IEEE]
        endpoint_id: int = service.data[ATTR_ENDPOINT_ID]
        cluster_id: int = service.data[ATTR_CLUSTER_ID]
        cluster_type: str = service.data[ATTR_CLUSTER_TYPE]
        command: int = service.data[ATTR_COMMAND]
        command_type: str = service.data[ATTR_COMMAND_TYPE]
        args: list | None = service.data.get(ATTR_ARGS)
        params: dict | None = service.data.get(ATTR_PARAMS)
        manufacturer: int | None = service.data.get(ATTR_MANUFACTURER)
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

    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_ISSUE_ZIGBEE_CLUSTER_COMMAND,
        issue_zigbee_cluster_command,
        schema=SERVICE_SCHEMAS[SERVICE_ISSUE_ZIGBEE_CLUSTER_COMMAND],
    )

    async def issue_zigbee_group_command(service: ServiceCall) -> None:
        """Issue command on zigbee cluster on a zigbee group."""
        group_id: int = service.data[ATTR_GROUP]
        cluster_id: int = service.data[ATTR_CLUSTER_ID]
        command: int = service.data[ATTR_COMMAND]
        args: list = service.data[ATTR_ARGS]
        manufacturer: int | None = service.data.get(ATTR_MANUFACTURER)
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

    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_ISSUE_ZIGBEE_GROUP_COMMAND,
        issue_zigbee_group_command,
        schema=SERVICE_SCHEMAS[SERVICE_ISSUE_ZIGBEE_GROUP_COMMAND],
    )

    def _get_ias_wd_cluster_handler(zha_device):
        """Get the IASWD cluster handler for a device."""
        cluster_handlers = {
            ch.name: ch
            for endpoint in zha_device.endpoints.values()
            for ch in endpoint.claimed_cluster_handlers.values()
        }
        return cluster_handlers.get(CLUSTER_HANDLER_IAS_WD)

    async def warning_device_squawk(service: ServiceCall) -> None:
        """Issue the squawk command for an IAS warning device."""
        ieee: EUI64 = service.data[ATTR_IEEE]
        mode: int = service.data[ATTR_WARNING_DEVICE_MODE]
        strobe: int = service.data[ATTR_WARNING_DEVICE_STROBE]
        level: int = service.data[ATTR_LEVEL]

        if (zha_device := zha_gateway.get_device(ieee)) is not None:
            if cluster_handler := _get_ias_wd_cluster_handler(zha_device):
                await cluster_handler.issue_squawk(mode, strobe, level)
            else:
                _LOGGER.error(
                    "Squawking IASWD: %s: [%s] is missing the required IASWD cluster handler!",
                    ATTR_IEEE,
                    str(ieee),
                )
        else:
            _LOGGER.error(
                "Squawking IASWD: %s: [%s] could not be found!", ATTR_IEEE, str(ieee)
            )
        _LOGGER.debug(
            "Squawking IASWD: %s: [%s] %s: [%s] %s: [%s] %s: [%s]",
            ATTR_IEEE,
            str(ieee),
            ATTR_WARNING_DEVICE_MODE,
            mode,
            ATTR_WARNING_DEVICE_STROBE,
            strobe,
            ATTR_LEVEL,
            level,
        )

    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_WARNING_DEVICE_SQUAWK,
        warning_device_squawk,
        schema=SERVICE_SCHEMAS[SERVICE_WARNING_DEVICE_SQUAWK],
    )

    async def warning_device_warn(service: ServiceCall) -> None:
        """Issue the warning command for an IAS warning device."""
        ieee: EUI64 = service.data[ATTR_IEEE]
        mode: int = service.data[ATTR_WARNING_DEVICE_MODE]
        strobe: int = service.data[ATTR_WARNING_DEVICE_STROBE]
        level: int = service.data[ATTR_LEVEL]
        duration: int = service.data[ATTR_WARNING_DEVICE_DURATION]
        duty_mode: int = service.data[ATTR_WARNING_DEVICE_STROBE_DUTY_CYCLE]
        intensity: int = service.data[ATTR_WARNING_DEVICE_STROBE_INTENSITY]

        if (zha_device := zha_gateway.get_device(ieee)) is not None:
            if cluster_handler := _get_ias_wd_cluster_handler(zha_device):
                await cluster_handler.issue_start_warning(
                    mode, strobe, level, duration, duty_mode, intensity
                )
            else:
                _LOGGER.error(
                    "Warning IASWD: %s: [%s] is missing the required IASWD cluster handler!",
                    ATTR_IEEE,
                    str(ieee),
                )
        else:
            _LOGGER.error(
                "Warning IASWD: %s: [%s] could not be found!", ATTR_IEEE, str(ieee)
            )
        _LOGGER.debug(
            "Warning IASWD: %s: [%s] %s: [%s] %s: [%s] %s: [%s]",
            ATTR_IEEE,
            str(ieee),
            ATTR_WARNING_DEVICE_MODE,
            mode,
            ATTR_WARNING_DEVICE_STROBE,
            strobe,
            ATTR_LEVEL,
            level,
        )

    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_WARNING_DEVICE_WARN,
        warning_device_warn,
        schema=SERVICE_SCHEMAS[SERVICE_WARNING_DEVICE_WARN],
    )

    websocket_api.async_register_command(hass, websocket_permit_devices)
    websocket_api.async_register_command(hass, websocket_get_devices)
    websocket_api.async_register_command(hass, websocket_get_groupable_devices)
    websocket_api.async_register_command(hass, websocket_get_groups)
    websocket_api.async_register_command(hass, websocket_get_device)
    websocket_api.async_register_command(hass, websocket_get_group)
    websocket_api.async_register_command(hass, websocket_add_group)
    websocket_api.async_register_command(hass, websocket_remove_groups)
    websocket_api.async_register_command(hass, websocket_add_group_members)
    websocket_api.async_register_command(hass, websocket_remove_group_members)
    websocket_api.async_register_command(hass, websocket_bind_group)
    websocket_api.async_register_command(hass, websocket_unbind_group)
    websocket_api.async_register_command(hass, websocket_reconfigure_node)
    websocket_api.async_register_command(hass, websocket_device_clusters)
    websocket_api.async_register_command(hass, websocket_device_cluster_attributes)
    websocket_api.async_register_command(hass, websocket_device_cluster_commands)
    websocket_api.async_register_command(hass, websocket_read_zigbee_cluster_attributes)
    websocket_api.async_register_command(hass, websocket_get_bindable_devices)
    websocket_api.async_register_command(hass, websocket_bind_devices)
    websocket_api.async_register_command(hass, websocket_unbind_devices)
    websocket_api.async_register_command(hass, websocket_update_topology)
    websocket_api.async_register_command(hass, websocket_get_configuration)
    websocket_api.async_register_command(hass, websocket_update_zha_configuration)
    websocket_api.async_register_command(hass, websocket_get_network_settings)
    websocket_api.async_register_command(hass, websocket_list_network_backups)
    websocket_api.async_register_command(hass, websocket_create_network_backup)
    websocket_api.async_register_command(hass, websocket_restore_network_backup)
    websocket_api.async_register_command(hass, websocket_change_channel)


@callback
def async_unload_api(hass: HomeAssistant) -> None:
    """Unload the ZHA API."""
    hass.services.async_remove(DOMAIN, SERVICE_PERMIT)
    hass.services.async_remove(DOMAIN, SERVICE_REMOVE)
    hass.services.async_remove(DOMAIN, SERVICE_SET_ZIGBEE_CLUSTER_ATTRIBUTE)
    hass.services.async_remove(DOMAIN, SERVICE_ISSUE_ZIGBEE_CLUSTER_COMMAND)
    hass.services.async_remove(DOMAIN, SERVICE_ISSUE_ZIGBEE_GROUP_COMMAND)
    hass.services.async_remove(DOMAIN, SERVICE_WARNING_DEVICE_SQUAWK)
    hass.services.async_remove(DOMAIN, SERVICE_WARNING_DEVICE_WARN)
