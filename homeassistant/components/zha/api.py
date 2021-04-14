"""Web socket API for Zigbee Home Automation devices."""

import asyncio
import collections
from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol
from zigpy.config.validators import cv_boolean
from zigpy.types.named import EUI64
from zigpy.zcl.clusters.security import IasAce
import zigpy.zdo.types as zdo_types

from homeassistant.components import websocket_api
from homeassistant.const import ATTR_COMMAND, ATTR_NAME
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect

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
    ATTR_VALUE,
    ATTR_WARNING_DEVICE_DURATION,
    ATTR_WARNING_DEVICE_MODE,
    ATTR_WARNING_DEVICE_STROBE,
    ATTR_WARNING_DEVICE_STROBE_DUTY_CYCLE,
    ATTR_WARNING_DEVICE_STROBE_INTENSITY,
    BINDINGS,
    CHANNEL_IAS_WD,
    CLUSTER_COMMAND_SERVER,
    CLUSTER_COMMANDS_CLIENT,
    CLUSTER_COMMANDS_SERVER,
    CLUSTER_TYPE_IN,
    CLUSTER_TYPE_OUT,
    CUSTOM_CONFIGURATION,
    DATA_ZHA,
    DATA_ZHA_GATEWAY,
    DOMAIN,
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
    ZHA_CONFIG_SCHEMAS,
)
from .core.group import GroupMember
from .core.helpers import (
    async_input_cluster_exists,
    async_is_bindable_target,
    convert_install_code,
    get_matched_clusters,
    qr_to_install_code,
)
from .core.typing import ZhaDeviceType, ZhaGatewayType

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

SERVICE_PERMIT_PARAMS = {
    vol.Optional(ATTR_IEEE, default=None): EUI64.convert,
    vol.Optional(ATTR_DURATION, default=60): vol.All(
        vol.Coerce(int), vol.Range(0, 254)
    ),
    vol.Inclusive(ATTR_SOURCE_IEEE, "install_code"): EUI64.convert,
    vol.Inclusive(ATTR_INSTALL_CODE, "install_code"): convert_install_code,
    vol.Exclusive(ATTR_QR_CODE, "install_code"): vol.All(str, qr_to_install_code),
}

SERVICE_SCHEMAS = {
    SERVICE_PERMIT: vol.Schema(
        vol.All(
            cv.deprecated(ATTR_IEEE_ADDRESS, replacement_key=ATTR_IEEE),
            SERVICE_PERMIT_PARAMS,
        )
    ),
    IEEE_SERVICE: vol.Schema(
        vol.All(
            cv.deprecated(ATTR_IEEE_ADDRESS, replacement_key=ATTR_IEEE),
            {vol.Required(ATTR_IEEE): EUI64.convert},
        )
    ),
    SERVICE_SET_ZIGBEE_CLUSTER_ATTRIBUTE: vol.Schema(
        {
            vol.Required(ATTR_IEEE): EUI64.convert,
            vol.Required(ATTR_ENDPOINT_ID): cv.positive_int,
            vol.Required(ATTR_CLUSTER_ID): cv.positive_int,
            vol.Optional(ATTR_CLUSTER_TYPE, default=CLUSTER_TYPE_IN): cv.string,
            vol.Required(ATTR_ATTRIBUTE): vol.Any(cv.positive_int, str),
            vol.Required(ATTR_VALUE): vol.Any(int, cv.boolean, cv.string),
            vol.Optional(ATTR_MANUFACTURER): cv.positive_int,
        }
    ),
    SERVICE_WARNING_DEVICE_SQUAWK: vol.Schema(
        {
            vol.Required(ATTR_IEEE): EUI64.convert,
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
            vol.Required(ATTR_IEEE): EUI64.convert,
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
    SERVICE_ISSUE_ZIGBEE_CLUSTER_COMMAND: vol.Schema(
        {
            vol.Required(ATTR_IEEE): EUI64.convert,
            vol.Required(ATTR_ENDPOINT_ID): cv.positive_int,
            vol.Required(ATTR_CLUSTER_ID): cv.positive_int,
            vol.Optional(ATTR_CLUSTER_TYPE, default=CLUSTER_TYPE_IN): cv.string,
            vol.Required(ATTR_COMMAND): cv.positive_int,
            vol.Required(ATTR_COMMAND_TYPE): cv.string,
            vol.Optional(ATTR_ARGS, default=[]): cv.ensure_list,
            vol.Optional(ATTR_MANUFACTURER): cv.positive_int,
        }
    ),
    SERVICE_ISSUE_ZIGBEE_GROUP_COMMAND: vol.Schema(
        {
            vol.Required(ATTR_GROUP): cv.positive_int,
            vol.Required(ATTR_CLUSTER_ID): cv.positive_int,
            vol.Optional(ATTR_CLUSTER_TYPE, default=CLUSTER_TYPE_IN): cv.string,
            vol.Required(ATTR_COMMAND): cv.positive_int,
            vol.Optional(ATTR_ARGS, default=[]): cv.ensure_list,
            vol.Optional(ATTR_MANUFACTURER): cv.positive_int,
        }
    ),
}

ClusterBinding = collections.namedtuple("ClusterBinding", "id endpoint_id type name")


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command(
    {vol.Required("type"): "zha/devices/permit", **SERVICE_PERMIT_PARAMS}
)
async def websocket_permit_devices(hass, connection, msg):
    """Permit ZHA zigbee devices."""
    zha_gateway = hass.data[DATA_ZHA][DATA_ZHA_GATEWAY]
    duration = msg.get(ATTR_DURATION)
    ieee = msg.get(ATTR_IEEE)

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
    if ATTR_SOURCE_IEEE in msg:
        src_ieee = msg[ATTR_SOURCE_IEEE]
        code = msg[ATTR_INSTALL_CODE]
        _LOGGER.debug("Allowing join for %s device with install code", src_ieee)
        await zha_gateway.application_controller.permit_with_key(
            time_s=duration, node=src_ieee, code=code
        )
    elif ATTR_QR_CODE in msg:
        src_ieee, code = msg[ATTR_QR_CODE]
        _LOGGER.debug("Allowing join for %s device with install code", src_ieee)
        await zha_gateway.application_controller.permit_with_key(
            time_s=duration, node=src_ieee, code=code
        )
    else:
        await zha_gateway.application_controller.permit(time_s=duration, node=ieee)
    connection.send_result(msg["id"])


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command({vol.Required(TYPE): "zha/devices"})
async def websocket_get_devices(hass, connection, msg):
    """Get ZHA devices."""
    zha_gateway = hass.data[DATA_ZHA][DATA_ZHA_GATEWAY]

    devices = [device.zha_device_info for device in zha_gateway.devices.values()]

    connection.send_result(msg[ID], devices)


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command({vol.Required(TYPE): "zha/devices/groupable"})
async def websocket_get_groupable_devices(hass, connection, msg):
    """Get ZHA devices that can be grouped."""
    zha_gateway = hass.data[DATA_ZHA][DATA_ZHA_GATEWAY]

    devices = [device for device in zha_gateway.devices.values() if device.is_groupable]
    groupable_devices = []

    for device in devices:
        entity_refs = zha_gateway.device_registry.get(device.ieee)
        for ep_id in device.async_get_groupable_endpoints():
            groupable_devices.append(
                {
                    "endpoint_id": ep_id,
                    "entities": [
                        {
                            "name": zha_gateway.ha_entity_registry.async_get(
                                entity_ref.reference_id
                            ).name,
                            "original_name": zha_gateway.ha_entity_registry.async_get(
                                entity_ref.reference_id
                            ).original_name,
                        }
                        for entity_ref in entity_refs
                        if list(entity_ref.cluster_channels.values())[
                            0
                        ].cluster.endpoint.endpoint_id
                        == ep_id
                    ],
                    "device": device.zha_device_info,
                }
            )

    connection.send_result(msg[ID], groupable_devices)


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command({vol.Required(TYPE): "zha/groups"})
async def websocket_get_groups(hass, connection, msg):
    """Get ZHA groups."""
    zha_gateway = hass.data[DATA_ZHA][DATA_ZHA_GATEWAY]
    groups = [group.group_info for group in zha_gateway.groups.values()]
    connection.send_result(msg[ID], groups)


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command(
    {vol.Required(TYPE): "zha/device", vol.Required(ATTR_IEEE): EUI64.convert}
)
async def websocket_get_device(hass, connection, msg):
    """Get ZHA devices."""
    zha_gateway = hass.data[DATA_ZHA][DATA_ZHA_GATEWAY]
    ieee = msg[ATTR_IEEE]
    device = None
    if ieee in zha_gateway.devices:
        device = zha_gateway.devices[ieee].zha_device_info
    if not device:
        connection.send_message(
            websocket_api.error_message(
                msg[ID], websocket_api.const.ERR_NOT_FOUND, "ZHA Device not found"
            )
        )
        return
    connection.send_result(msg[ID], device)


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command(
    {vol.Required(TYPE): "zha/group", vol.Required(GROUP_ID): cv.positive_int}
)
async def websocket_get_group(hass, connection, msg):
    """Get ZHA group."""
    zha_gateway = hass.data[DATA_ZHA][DATA_ZHA_GATEWAY]
    group_id = msg[GROUP_ID]
    group = None

    if group_id in zha_gateway.groups:
        group = zha_gateway.groups.get(group_id).group_info
    if not group:
        connection.send_message(
            websocket_api.error_message(
                msg[ID], websocket_api.const.ERR_NOT_FOUND, "ZHA Group not found"
            )
        )
        return
    connection.send_result(msg[ID], group)


def cv_group_member(value: Any) -> GroupMember:
    """Validate and transform a group member."""
    if not isinstance(value, Mapping):
        raise vol.Invalid("Not a group member")
    try:
        group_member = GroupMember(
            ieee=EUI64.convert(value["ieee"]), endpoint_id=value["endpoint_id"]
        )
    except KeyError as err:
        raise vol.Invalid("Not a group member") from err

    return group_member


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zha/group/add",
        vol.Required(GROUP_NAME): cv.string,
        vol.Optional(ATTR_MEMBERS): vol.All(cv.ensure_list, [cv_group_member]),
    }
)
async def websocket_add_group(hass, connection, msg):
    """Add a new ZHA group."""
    zha_gateway = hass.data[DATA_ZHA][DATA_ZHA_GATEWAY]
    group_name = msg[GROUP_NAME]
    members = msg.get(ATTR_MEMBERS)
    group = await zha_gateway.async_create_zigpy_group(group_name, members)
    connection.send_result(msg[ID], group.group_info)


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zha/group/remove",
        vol.Required(GROUP_IDS): vol.All(cv.ensure_list, [cv.positive_int]),
    }
)
async def websocket_remove_groups(hass, connection, msg):
    """Remove the specified ZHA groups."""
    zha_gateway = hass.data[DATA_ZHA][DATA_ZHA_GATEWAY]
    group_ids = msg[GROUP_IDS]

    if len(group_ids) > 1:
        tasks = []
        for group_id in group_ids:
            tasks.append(zha_gateway.async_remove_zigpy_group(group_id))
        await asyncio.gather(*tasks)
    else:
        await zha_gateway.async_remove_zigpy_group(group_ids[0])
    ret_groups = [group.group_info for group in zha_gateway.groups.values()]
    connection.send_result(msg[ID], ret_groups)


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zha/group/members/add",
        vol.Required(GROUP_ID): cv.positive_int,
        vol.Required(ATTR_MEMBERS): vol.All(cv.ensure_list, [cv_group_member]),
    }
)
async def websocket_add_group_members(hass, connection, msg):
    """Add members to a ZHA group."""
    zha_gateway = hass.data[DATA_ZHA][DATA_ZHA_GATEWAY]
    group_id = msg[GROUP_ID]
    members = msg[ATTR_MEMBERS]
    zha_group = None

    if group_id in zha_gateway.groups:
        zha_group = zha_gateway.groups.get(group_id)
        await zha_group.async_add_members(members)
    if not zha_group:
        connection.send_message(
            websocket_api.error_message(
                msg[ID], websocket_api.const.ERR_NOT_FOUND, "ZHA Group not found"
            )
        )
        return
    ret_group = zha_group.group_info
    connection.send_result(msg[ID], ret_group)


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zha/group/members/remove",
        vol.Required(GROUP_ID): cv.positive_int,
        vol.Required(ATTR_MEMBERS): vol.All(cv.ensure_list, [cv_group_member]),
    }
)
async def websocket_remove_group_members(hass, connection, msg):
    """Remove members from a ZHA group."""
    zha_gateway = hass.data[DATA_ZHA][DATA_ZHA_GATEWAY]
    group_id = msg[GROUP_ID]
    members = msg[ATTR_MEMBERS]
    zha_group = None

    if group_id in zha_gateway.groups:
        zha_group = zha_gateway.groups.get(group_id)
        await zha_group.async_remove_members(members)
    if not zha_group:
        connection.send_message(
            websocket_api.error_message(
                msg[ID], websocket_api.const.ERR_NOT_FOUND, "ZHA Group not found"
            )
        )
        return
    ret_group = zha_group.group_info
    connection.send_result(msg[ID], ret_group)


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zha/devices/reconfigure",
        vol.Required(ATTR_IEEE): EUI64.convert,
    }
)
async def websocket_reconfigure_node(hass, connection, msg):
    """Reconfigure a ZHA nodes entities by its ieee address."""
    zha_gateway: ZhaGatewayType = hass.data[DATA_ZHA][DATA_ZHA_GATEWAY]
    ieee = msg[ATTR_IEEE]
    device: ZhaDeviceType = zha_gateway.get_device(ieee)
    ieee_str = str(device.ieee)
    nwk_str = device.nwk.__repr__()

    class DeviceLogFilterer(logging.Filter):
        """Log filterer that limits messages to the specified device."""

        def filter(self, record):
            message = record.getMessage()
            return nwk_str in message or ieee_str in message

    filterer = DeviceLogFilterer()

    async def forward_messages(data):
        """Forward events to websocket."""
        connection.send_message(websocket_api.event_message(msg["id"], data))

    remove_dispatcher_function = async_dispatcher_connect(
        hass, "zha_gateway_message", forward_messages
    )

    @callback
    def async_cleanup() -> None:
        """Remove signal listener and turn off debug mode."""
        zha_gateway.async_disable_debug_mode(filterer=filterer)
        remove_dispatcher_function()

    connection.subscriptions[msg["id"]] = async_cleanup
    zha_gateway.async_enable_debug_mode(filterer=filterer)

    _LOGGER.debug("Reconfiguring node with ieee_address: %s", ieee)
    hass.async_create_task(device.async_configure())


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zha/topology/update",
    }
)
async def websocket_update_topology(hass, connection, msg):
    """Update the ZHA network topology."""
    zha_gateway = hass.data[DATA_ZHA][DATA_ZHA_GATEWAY]
    hass.async_create_task(zha_gateway.application_controller.topology.scan())


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command(
    {vol.Required(TYPE): "zha/devices/clusters", vol.Required(ATTR_IEEE): EUI64.convert}
)
async def websocket_device_clusters(hass, connection, msg):
    """Return a list of device clusters."""
    zha_gateway = hass.data[DATA_ZHA][DATA_ZHA_GATEWAY]
    ieee = msg[ATTR_IEEE]
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
@websocket_api.async_response
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zha/devices/clusters/attributes",
        vol.Required(ATTR_IEEE): EUI64.convert,
        vol.Required(ATTR_ENDPOINT_ID): int,
        vol.Required(ATTR_CLUSTER_ID): int,
        vol.Required(ATTR_CLUSTER_TYPE): str,
    }
)
async def websocket_device_cluster_attributes(hass, connection, msg):
    """Return a list of cluster attributes."""
    zha_gateway = hass.data[DATA_ZHA][DATA_ZHA_GATEWAY]
    ieee = msg[ATTR_IEEE]
    endpoint_id = msg[ATTR_ENDPOINT_ID]
    cluster_id = msg[ATTR_CLUSTER_ID]
    cluster_type = msg[ATTR_CLUSTER_TYPE]
    cluster_attributes = []
    zha_device = zha_gateway.get_device(ieee)
    attributes = None
    if zha_device is not None:
        attributes = zha_device.async_get_cluster_attributes(
            endpoint_id, cluster_id, cluster_type
        )
        if attributes is not None:
            for attr_id in attributes:
                cluster_attributes.append(
                    {ID: attr_id, ATTR_NAME: attributes[attr_id][0]}
                )
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
@websocket_api.async_response
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zha/devices/clusters/commands",
        vol.Required(ATTR_IEEE): EUI64.convert,
        vol.Required(ATTR_ENDPOINT_ID): int,
        vol.Required(ATTR_CLUSTER_ID): int,
        vol.Required(ATTR_CLUSTER_TYPE): str,
    }
)
async def websocket_device_cluster_commands(hass, connection, msg):
    """Return a list of cluster commands."""
    zha_gateway = hass.data[DATA_ZHA][DATA_ZHA_GATEWAY]
    cluster_id = msg[ATTR_CLUSTER_ID]
    cluster_type = msg[ATTR_CLUSTER_TYPE]
    ieee = msg[ATTR_IEEE]
    endpoint_id = msg[ATTR_ENDPOINT_ID]
    zha_device = zha_gateway.get_device(ieee)
    cluster_commands = []
    commands = None
    if zha_device is not None:
        commands = zha_device.async_get_cluster_commands(
            endpoint_id, cluster_id, cluster_type
        )

        if commands is not None:
            for cmd_id in commands[CLUSTER_COMMANDS_CLIENT]:
                cluster_commands.append(
                    {
                        TYPE: CLIENT,
                        ID: cmd_id,
                        ATTR_NAME: commands[CLUSTER_COMMANDS_CLIENT][cmd_id][0],
                    }
                )
            for cmd_id in commands[CLUSTER_COMMANDS_SERVER]:
                cluster_commands.append(
                    {
                        TYPE: CLUSTER_COMMAND_SERVER,
                        ID: cmd_id,
                        ATTR_NAME: commands[CLUSTER_COMMANDS_SERVER][cmd_id][0],
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
@websocket_api.async_response
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zha/devices/clusters/attributes/value",
        vol.Required(ATTR_IEEE): EUI64.convert,
        vol.Required(ATTR_ENDPOINT_ID): int,
        vol.Required(ATTR_CLUSTER_ID): int,
        vol.Required(ATTR_CLUSTER_TYPE): str,
        vol.Required(ATTR_ATTRIBUTE): int,
        vol.Optional(ATTR_MANUFACTURER): object,
    }
)
async def websocket_read_zigbee_cluster_attributes(hass, connection, msg):
    """Read zigbee attribute for cluster on zha entity."""
    zha_gateway = hass.data[DATA_ZHA][DATA_ZHA_GATEWAY]
    ieee = msg[ATTR_IEEE]
    endpoint_id = msg[ATTR_ENDPOINT_ID]
    cluster_id = msg[ATTR_CLUSTER_ID]
    cluster_type = msg[ATTR_CLUSTER_TYPE]
    attribute = msg[ATTR_ATTRIBUTE]
    manufacturer = msg.get(ATTR_MANUFACTURER) or None
    zha_device = zha_gateway.get_device(ieee)
    if cluster_id >= MFG_CLUSTER_ID_START and manufacturer is None:
        manufacturer = zha_device.manufacturer_code
    success = failure = None
    if zha_device is not None:
        cluster = zha_device.async_get_cluster(
            endpoint_id, cluster_id, cluster_type=cluster_type
        )
        success, failure = await cluster.read_attributes(
            [attribute], allow_cache=False, only_cache=False, manufacturer=manufacturer
        )
    _LOGGER.debug(
        "Read attribute for: %s: [%s] %s: [%s] %s: [%s] %s: [%s] %s: [%s] %s: [%s] %s: [%s],",
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
@websocket_api.async_response
@websocket_api.websocket_command(
    {vol.Required(TYPE): "zha/devices/bindable", vol.Required(ATTR_IEEE): EUI64.convert}
)
async def websocket_get_bindable_devices(hass, connection, msg):
    """Directly bind devices."""
    zha_gateway = hass.data[DATA_ZHA][DATA_ZHA_GATEWAY]
    source_ieee = msg[ATTR_IEEE]
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
@websocket_api.async_response
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zha/devices/bind",
        vol.Required(ATTR_SOURCE_IEEE): EUI64.convert,
        vol.Required(ATTR_TARGET_IEEE): EUI64.convert,
    }
)
async def websocket_bind_devices(hass, connection, msg):
    """Directly bind devices."""
    zha_gateway = hass.data[DATA_ZHA][DATA_ZHA_GATEWAY]
    source_ieee = msg[ATTR_SOURCE_IEEE]
    target_ieee = msg[ATTR_TARGET_IEEE]
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


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zha/devices/unbind",
        vol.Required(ATTR_SOURCE_IEEE): EUI64.convert,
        vol.Required(ATTR_TARGET_IEEE): EUI64.convert,
    }
)
async def websocket_unbind_devices(hass, connection, msg):
    """Remove a direct binding between devices."""
    zha_gateway = hass.data[DATA_ZHA][DATA_ZHA_GATEWAY]
    source_ieee = msg[ATTR_SOURCE_IEEE]
    target_ieee = msg[ATTR_TARGET_IEEE]
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


def is_cluster_binding(value: Any) -> ClusterBinding:
    """Validate and transform a cluster binding."""
    if not isinstance(value, Mapping):
        raise vol.Invalid("Not a cluster binding")
    try:
        cluster_binding = ClusterBinding(
            name=value["name"],
            type=value["type"],
            id=value["id"],
            endpoint_id=value["endpoint_id"],
        )
    except KeyError as err:
        raise vol.Invalid("Not a cluster binding") from err

    return cluster_binding


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zha/groups/bind",
        vol.Required(ATTR_SOURCE_IEEE): EUI64.convert,
        vol.Required(GROUP_ID): cv.positive_int,
        vol.Required(BINDINGS): vol.All(cv.ensure_list, [is_cluster_binding]),
    }
)
async def websocket_bind_group(hass, connection, msg):
    """Directly bind a device to a group."""
    zha_gateway = hass.data[DATA_ZHA][DATA_ZHA_GATEWAY]
    source_ieee = msg[ATTR_SOURCE_IEEE]
    group_id = msg[GROUP_ID]
    bindings = msg[BINDINGS]
    source_device = zha_gateway.get_device(source_ieee)

    await source_device.async_bind_to_group(group_id, bindings)


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zha/groups/unbind",
        vol.Required(ATTR_SOURCE_IEEE): EUI64.convert,
        vol.Required(GROUP_ID): cv.positive_int,
        vol.Required(BINDINGS): vol.All(cv.ensure_list, [is_cluster_binding]),
    }
)
async def websocket_unbind_group(hass, connection, msg):
    """Unbind a device from a group."""
    zha_gateway = hass.data[DATA_ZHA][DATA_ZHA_GATEWAY]
    source_ieee = msg[ATTR_SOURCE_IEEE]
    group_id = msg[GROUP_ID]
    bindings = msg[BINDINGS]
    source_device = zha_gateway.get_device(source_ieee)
    await source_device.async_unbind_from_group(group_id, bindings)


async def async_binding_operation(zha_gateway, source_ieee, target_ieee, operation):
    """Create or remove a direct zigbee binding between 2 devices."""

    source_device = zha_gateway.get_device(source_ieee)
    target_device = zha_gateway.get_device(target_ieee)

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
    for outcome, log_msg in zip(res, bind_tasks):
        if isinstance(outcome, Exception):
            fmt = f"{log_msg[1]} failed: %s"
        else:
            fmt = f"{log_msg[1]} completed: %s"
        zdo.debug(fmt, *(log_msg[2] + (outcome,)))


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command({vol.Required(TYPE): "zha/configuration"})
async def websocket_get_configuration(hass, connection, msg):
    """Get ZHA configuration."""
    zha_gateway = hass.data[DATA_ZHA][DATA_ZHA_GATEWAY]
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

    data = {"schemas": {}, "data": {}}
    for section, schema in ZHA_CONFIG_SCHEMAS.items():
        if section == ZHA_ALARM_OPTIONS and not async_input_cluster_exists(
            hass, IasAce.cluster_id
        ):
            continue
        data["schemas"][section] = voluptuous_serialize.convert(
            schema, custom_serializer=custom_serializer
        )
        data["data"][section] = zha_gateway.config_entry.options.get(
            CUSTOM_CONFIGURATION, {}
        ).get(section, {})
    connection.send_result(msg[ID], data)


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zha/configuration/update",
        vol.Required("data"): ZHA_CONFIG_SCHEMAS,
    }
)
async def websocket_update_zha_configuration(hass, connection, msg):
    """Update the ZHA configuration."""
    zha_gateway = hass.data[DATA_ZHA][DATA_ZHA_GATEWAY]
    options = zha_gateway.config_entry.options
    data_to_save = {**options, **{CUSTOM_CONFIGURATION: msg["data"]}}

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


@callback
def async_load_api(hass):
    """Set up the web socket API."""
    zha_gateway = hass.data[DATA_ZHA][DATA_ZHA_GATEWAY]
    application_controller = zha_gateway.application_controller

    async def permit(service):
        """Allow devices to join this network."""
        duration = service.data[ATTR_DURATION]
        ieee = service.data.get(ATTR_IEEE)
        if ATTR_SOURCE_IEEE in service.data:
            src_ieee = service.data[ATTR_SOURCE_IEEE]
            code = service.data[ATTR_INSTALL_CODE]
            _LOGGER.info("Allowing join for %s device with install code", src_ieee)
            await application_controller.permit_with_key(
                time_s=duration, node=src_ieee, code=code
            )
            return

        if ATTR_QR_CODE in service.data:
            src_ieee, code = service.data[ATTR_QR_CODE]
            _LOGGER.info("Allowing join for %s device with install code", src_ieee)
            await application_controller.permit_with_key(
                time_s=duration, node=src_ieee, code=code
            )
            return

        if ieee:
            _LOGGER.info("Permitting joins for %ss on %s device", duration, ieee)
        else:
            _LOGGER.info("Permitting joins for %ss", duration)
        await application_controller.permit(time_s=duration, node=ieee)

    hass.helpers.service.async_register_admin_service(
        DOMAIN, SERVICE_PERMIT, permit, schema=SERVICE_SCHEMAS[SERVICE_PERMIT]
    )

    async def remove(service):
        """Remove a node from the network."""
        ieee = service.data[ATTR_IEEE]
        zha_gateway: ZhaGatewayType = hass.data[DATA_ZHA][DATA_ZHA_GATEWAY]
        zha_device: ZhaDeviceType = zha_gateway.get_device(ieee)
        if zha_device is not None and (
            zha_device.is_coordinator
            and zha_device.ieee == zha_gateway.application_controller.ieee
        ):
            _LOGGER.info("Removing the coordinator (%s) is not allowed", ieee)
            return
        _LOGGER.info("Removing node %s", ieee)
        await application_controller.remove(ieee)

    hass.helpers.service.async_register_admin_service(
        DOMAIN, SERVICE_REMOVE, remove, schema=SERVICE_SCHEMAS[IEEE_SERVICE]
    )

    async def set_zigbee_cluster_attributes(service):
        """Set zigbee attribute for cluster on zha entity."""
        ieee = service.data.get(ATTR_IEEE)
        endpoint_id = service.data.get(ATTR_ENDPOINT_ID)
        cluster_id = service.data.get(ATTR_CLUSTER_ID)
        cluster_type = service.data.get(ATTR_CLUSTER_TYPE)
        attribute = service.data.get(ATTR_ATTRIBUTE)
        value = service.data.get(ATTR_VALUE)
        manufacturer = service.data.get(ATTR_MANUFACTURER) or None
        zha_device = zha_gateway.get_device(ieee)
        if cluster_id >= MFG_CLUSTER_ID_START and manufacturer is None:
            manufacturer = zha_device.manufacturer_code
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
        _LOGGER.debug(
            "Set attribute for: %s: [%s] %s: [%s] %s: [%s] %s: [%s] %s: [%s] %s: [%s] %s: [%s]",
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

    hass.helpers.service.async_register_admin_service(
        DOMAIN,
        SERVICE_SET_ZIGBEE_CLUSTER_ATTRIBUTE,
        set_zigbee_cluster_attributes,
        schema=SERVICE_SCHEMAS[SERVICE_SET_ZIGBEE_CLUSTER_ATTRIBUTE],
    )

    async def issue_zigbee_cluster_command(service):
        """Issue command on zigbee cluster on zha entity."""
        ieee = service.data.get(ATTR_IEEE)
        endpoint_id = service.data.get(ATTR_ENDPOINT_ID)
        cluster_id = service.data.get(ATTR_CLUSTER_ID)
        cluster_type = service.data.get(ATTR_CLUSTER_TYPE)
        command = service.data.get(ATTR_COMMAND)
        command_type = service.data.get(ATTR_COMMAND_TYPE)
        args = service.data.get(ATTR_ARGS)
        manufacturer = service.data.get(ATTR_MANUFACTURER) or None
        zha_device = zha_gateway.get_device(ieee)
        if cluster_id >= MFG_CLUSTER_ID_START and manufacturer is None:
            manufacturer = zha_device.manufacturer_code
        response = None
        if zha_device is not None:
            response = await zha_device.issue_cluster_command(
                endpoint_id,
                cluster_id,
                command,
                command_type,
                *args,
                cluster_type=cluster_type,
                manufacturer=manufacturer,
            )
        _LOGGER.debug(
            "Issued command for: %s: [%s] %s: [%s] %s: [%s] %s: [%s] %s: [%s] %s: %s %s: [%s] %s: %s",
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
            ATTR_MANUFACTURER,
            manufacturer,
            RESPONSE,
            response,
        )

    hass.helpers.service.async_register_admin_service(
        DOMAIN,
        SERVICE_ISSUE_ZIGBEE_CLUSTER_COMMAND,
        issue_zigbee_cluster_command,
        schema=SERVICE_SCHEMAS[SERVICE_ISSUE_ZIGBEE_CLUSTER_COMMAND],
    )

    async def issue_zigbee_group_command(service):
        """Issue command on zigbee cluster on a zigbee group."""
        group_id = service.data.get(ATTR_GROUP)
        cluster_id = service.data.get(ATTR_CLUSTER_ID)
        command = service.data.get(ATTR_COMMAND)
        args = service.data.get(ATTR_ARGS)
        manufacturer = service.data.get(ATTR_MANUFACTURER) or None
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

    hass.helpers.service.async_register_admin_service(
        DOMAIN,
        SERVICE_ISSUE_ZIGBEE_GROUP_COMMAND,
        issue_zigbee_group_command,
        schema=SERVICE_SCHEMAS[SERVICE_ISSUE_ZIGBEE_GROUP_COMMAND],
    )

    def _get_ias_wd_channel(zha_device):
        """Get the IASWD channel for a device."""
        cluster_channels = {
            ch.name: ch
            for pool in zha_device.channels.pools
            for ch in pool.claimed_channels.values()
        }
        return cluster_channels.get(CHANNEL_IAS_WD)

    async def warning_device_squawk(service):
        """Issue the squawk command for an IAS warning device."""
        ieee = service.data[ATTR_IEEE]
        mode = service.data.get(ATTR_WARNING_DEVICE_MODE)
        strobe = service.data.get(ATTR_WARNING_DEVICE_STROBE)
        level = service.data.get(ATTR_LEVEL)

        zha_device = zha_gateway.get_device(ieee)
        if zha_device is not None:
            channel = _get_ias_wd_channel(zha_device)
            if channel:
                await channel.issue_squawk(mode, strobe, level)
            else:
                _LOGGER.error(
                    "Squawking IASWD: %s: [%s] is missing the required IASWD channel!",
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

    hass.helpers.service.async_register_admin_service(
        DOMAIN,
        SERVICE_WARNING_DEVICE_SQUAWK,
        warning_device_squawk,
        schema=SERVICE_SCHEMAS[SERVICE_WARNING_DEVICE_SQUAWK],
    )

    async def warning_device_warn(service):
        """Issue the warning command for an IAS warning device."""
        ieee = service.data[ATTR_IEEE]
        mode = service.data.get(ATTR_WARNING_DEVICE_MODE)
        strobe = service.data.get(ATTR_WARNING_DEVICE_STROBE)
        level = service.data.get(ATTR_LEVEL)
        duration = service.data.get(ATTR_WARNING_DEVICE_DURATION)
        duty_mode = service.data.get(ATTR_WARNING_DEVICE_STROBE_DUTY_CYCLE)
        intensity = service.data.get(ATTR_WARNING_DEVICE_STROBE_INTENSITY)

        zha_device = zha_gateway.get_device(ieee)
        if zha_device is not None:
            channel = _get_ias_wd_channel(zha_device)
            if channel:
                await channel.issue_start_warning(
                    mode, strobe, level, duration, duty_mode, intensity
                )
            else:
                _LOGGER.error(
                    "Warning IASWD: %s: [%s] is missing the required IASWD channel!",
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

    hass.helpers.service.async_register_admin_service(
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


@callback
def async_unload_api(hass):
    """Unload the ZHA API."""
    hass.services.async_remove(DOMAIN, SERVICE_PERMIT)
    hass.services.async_remove(DOMAIN, SERVICE_REMOVE)
    hass.services.async_remove(DOMAIN, SERVICE_SET_ZIGBEE_CLUSTER_ATTRIBUTE)
    hass.services.async_remove(DOMAIN, SERVICE_ISSUE_ZIGBEE_CLUSTER_COMMAND)
    hass.services.async_remove(DOMAIN, SERVICE_ISSUE_ZIGBEE_GROUP_COMMAND)
    hass.services.async_remove(DOMAIN, SERVICE_WARNING_DEVICE_SQUAWK)
    hass.services.async_remove(DOMAIN, SERVICE_WARNING_DEVICE_WARN)
