"""Web socket API for OpenZWave."""

import logging

from openzwavemqtt.const import (
    EVENT_NODE_ADDED,
    EVENT_NODE_CHANGED,
    CommandClass,
    ValueType,
)
import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import callback

from .const import DOMAIN, MANAGER, OPTIONS
from .entity import set_config_parameter

_LOGGER = logging.getLogger(__name__)

TYPE = "type"
ID = "id"
OZW_INSTANCE = "ozw_instance"
NODE_ID = "node_id"
NODE_INSTANCE_ID = "node_instance_id"

ATTR_NODE_QUERY_STAGE = "node_query_stage"
ATTR_IS_ZWAVE_PLUS = "is_zwave_plus"
ATTR_IS_AWAKE = "is_awake"
ATTR_IS_FAILED = "is_failed"
ATTR_NODE_BAUD_RATE = "node_baud_rate"
ATTR_IS_BEAMING = "is_beaming"
ATTR_IS_FLIRS = "is_flirs"
ATTR_IS_ROUTING = "is_routing"
ATTR_IS_SECURITYV1 = "is_securityv1"
ATTR_NODE_BASIC_STRING = "node_basic_string"
ATTR_NODE_GENERIC_STRING = "node_generic_string"
ATTR_NODE_SPECIFIC_STRING = "node_specific_string"
ATTR_NODE_MANUFACTURER_NAME = "node_manufacturer_name"
ATTR_NODE_PRODUCT_NAME = "node_product_name"
ATTR_NEIGHBORS = "neighbors"
ATTR_INDEX = "index"
ATTR_LABEL = "label"
ATTR_MAX = "max"
ATTR_MIN = "min"
ATTR_OPTIONS = "options"
ATTR_TYPE = "type"
ATTR_VALUE = "value"


@callback
def async_register_api(hass):
    """Register all of our api endpoints."""
    websocket_api.async_register_command(hass, websocket_get_instances)
    websocket_api.async_register_command(hass, websocket_get_nodes)
    websocket_api.async_register_command(hass, websocket_network_status)
    websocket_api.async_register_command(hass, websocket_network_statistics)
    websocket_api.async_register_command(hass, websocket_node_metadata)
    websocket_api.async_register_command(hass, websocket_node_status)
    websocket_api.async_register_command(hass, websocket_node_statistics)
    websocket_api.async_register_command(hass, websocket_refresh_node_info)
    websocket_api.async_register_command(hass, websocket_get_config_parameters)
    websocket_api.async_register_command(hass, websocket_set_config_parameter)


@websocket_api.websocket_command({vol.Required(TYPE): "ozw/get_instances"})
def websocket_get_instances(hass, connection, msg):
    """Get a list of OZW instances."""
    manager = hass.data[DOMAIN][MANAGER]
    instances = []

    for instance in manager.collections["instance"]:
        instances.append(dict(instance.get_status().data, ozw_instance=instance.id))

    connection.send_result(
        msg[ID],
        instances,
    )


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "ozw/get_nodes",
        vol.Optional(OZW_INSTANCE, default=1): vol.Coerce(int),
    }
)
def websocket_get_nodes(hass, connection, msg):
    """Get a list of nodes for an OZW instance."""
    manager = hass.data[DOMAIN][MANAGER]
    nodes = []

    for node in manager.get_instance(msg[OZW_INSTANCE]).collections["node"]:
        nodes.append(
            {
                ATTR_NODE_QUERY_STAGE: node.node_query_stage,
                NODE_ID: node.node_id,
                ATTR_IS_ZWAVE_PLUS: node.is_zwave_plus,
                ATTR_IS_AWAKE: node.is_awake,
                ATTR_IS_FAILED: node.is_failed,
                ATTR_NODE_BAUD_RATE: node.node_baud_rate,
                ATTR_IS_BEAMING: node.is_beaming,
                ATTR_IS_FLIRS: node.is_flirs,
                ATTR_IS_ROUTING: node.is_routing,
                ATTR_IS_SECURITYV1: node.is_securityv1,
                ATTR_NODE_BASIC_STRING: node.node_basic_string,
                ATTR_NODE_GENERIC_STRING: node.node_generic_string,
                ATTR_NODE_SPECIFIC_STRING: node.node_specific_string,
                ATTR_NODE_MANUFACTURER_NAME: node.node_manufacturer_name,
                ATTR_NODE_PRODUCT_NAME: node.node_product_name,
                ATTR_NEIGHBORS: node.neighbors,
                OZW_INSTANCE: msg[OZW_INSTANCE],
            }
        )

    connection.send_result(
        msg[ID],
        nodes,
    )


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "ozw/get_config_parameters",
        vol.Required(NODE_ID): vol.Coerce(int),
        vol.Optional(OZW_INSTANCE, default=1): vol.Coerce(int),
        vol.Optional(NODE_INSTANCE_ID): vol.Coerce(int),
    }
)
def websocket_get_config_parameters(hass, connection, msg):
    """Get a list of configuration parameters for an OZW node instance."""
    manager = hass.data[DOMAIN][MANAGER]
    node = manager.get_instance(msg[OZW_INSTANCE]).get_node(msg[NODE_ID])
    command_class = node.get_command_class(
        CommandClass.CONFIGURATION, msg.get(NODE_INSTANCE_ID)
    )
    if not command_class:
        connection.send_message(
            websocket_api.error_message(
                msg[ID],
                websocket_api.const.ERR_NOT_FOUND,
                "Configuration parameters for OZW Node Instance not found",
            )
        )
        return

    values = []

    for value in command_class.values():
        value_to_return = {}
        if value.read_only or value.type == ValueType.BUTTON:
            continue

        value_to_return = {
            ATTR_LABEL: value.label,
            ATTR_TYPE: str(value.type),
            ATTR_INDEX: value.index,
        }

        if value.type == ValueType.BOOL:
            value_to_return[ATTR_VALUE] = value.value["Value"]

        if value.type == ValueType.LIST:
            value_to_return[ATTR_VALUE] = value.value["Selected"]
            value_to_return[ATTR_OPTIONS] = value.value["List"]

        if value.type == ValueType.STRING:
            value_to_return[ATTR_VALUE] = value.value

        if (
            value.type == ValueType.INT
            or value.type == ValueType.BYTE
            or value.type == ValueType.SHORT
        ):
            value_to_return[ATTR_VALUE] = int(value.value)
            value_to_return[ATTR_MAX] = value.max
            value_to_return[ATTR_MIN] = value.min

        values.append(value_to_return)

    connection.send_result(
        msg[ID],
        values,
    )


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "ozw/set_config_parameter",
        vol.Required(NODE_ID): vol.Coerce(int),
        vol.Optional(OZW_INSTANCE, default=1): vol.Coerce(int),
        vol.Optional(NODE_INSTANCE_ID): vol.Coerce(int),
        vol.Required(ATTR_INDEX): vol.Coerce(int),
        vol.Required(ATTR_VALUE): vol.Or(vol.Coerce(int), bool, str),
    }
)
def websocket_set_config_parameter(hass, connection, msg):
    """Set a config parameter to a node."""
    success, _, err_type, err_msg = set_config_parameter(
        hass.data[DOMAIN][MANAGER],
        msg[OZW_INSTANCE],
        msg[NODE_ID],
        msg[ATTR_INDEX],
        msg[ATTR_VALUE],
        msg.get(NODE_INSTANCE_ID),
    )

    if not success:
        connection.send_result(websocket_api.error_message(msg[ID], err_type, err_msg))
        return

    connection.send_result(msg[ID])


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "ozw/network_status",
        vol.Optional(OZW_INSTANCE, default=1): vol.Coerce(int),
    }
)
def websocket_network_status(hass, connection, msg):
    """Get Z-Wave network status."""

    manager = hass.data[DOMAIN][MANAGER]
    status = manager.get_instance(msg[OZW_INSTANCE]).get_status().data
    connection.send_result(
        msg[ID],
        dict(status, ozw_instance=msg[OZW_INSTANCE]),
    )


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "ozw/network_statistics",
        vol.Optional(OZW_INSTANCE, default=1): vol.Coerce(int),
    }
)
def websocket_network_statistics(hass, connection, msg):
    """Get Z-Wave network statistics."""

    manager = hass.data[DOMAIN][MANAGER]
    statistics = manager.get_instance(msg[OZW_INSTANCE]).get_statistics().data
    node_count = len(
        manager.get_instance(msg[OZW_INSTANCE]).collections["node"].collection
    )
    connection.send_result(
        msg[ID],
        dict(statistics, ozw_instance=msg[OZW_INSTANCE], node_count=node_count),
    )


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "ozw/node_status",
        vol.Required(NODE_ID): vol.Coerce(int),
        vol.Optional(OZW_INSTANCE, default=1): vol.Coerce(int),
    }
)
def websocket_node_status(hass, connection, msg):
    """Get the status for a Z-Wave node."""
    manager = hass.data[DOMAIN][MANAGER]
    node = manager.get_instance(msg[OZW_INSTANCE]).get_node(msg[NODE_ID])

    if not node:
        connection.send_message(
            websocket_api.error_message(
                msg[ID], websocket_api.const.ERR_NOT_FOUND, "OZW Node not found"
            )
        )
        return

    connection.send_result(
        msg[ID],
        {
            ATTR_NODE_QUERY_STAGE: node.node_query_stage,
            NODE_ID: node.node_id,
            ATTR_IS_ZWAVE_PLUS: node.is_zwave_plus,
            ATTR_IS_AWAKE: node.is_awake,
            ATTR_IS_FAILED: node.is_failed,
            ATTR_NODE_BAUD_RATE: node.node_baud_rate,
            ATTR_IS_BEAMING: node.is_beaming,
            ATTR_IS_FLIRS: node.is_flirs,
            ATTR_IS_ROUTING: node.is_routing,
            ATTR_IS_SECURITYV1: node.is_securityv1,
            ATTR_NODE_BASIC_STRING: node.node_basic_string,
            ATTR_NODE_GENERIC_STRING: node.node_generic_string,
            ATTR_NODE_SPECIFIC_STRING: node.node_specific_string,
            ATTR_NODE_MANUFACTURER_NAME: node.node_manufacturer_name,
            ATTR_NODE_PRODUCT_NAME: node.node_product_name,
            ATTR_NEIGHBORS: node.neighbors,
            OZW_INSTANCE: msg[OZW_INSTANCE],
        },
    )


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "ozw/node_metadata",
        vol.Required(NODE_ID): vol.Coerce(int),
        vol.Optional(OZW_INSTANCE, default=1): vol.Coerce(int),
    }
)
def websocket_node_metadata(hass, connection, msg):
    """Get the metadata for a Z-Wave node."""
    manager = hass.data[DOMAIN][MANAGER]
    node = manager.get_instance(msg[OZW_INSTANCE]).get_node(msg[NODE_ID])

    if not node:
        connection.send_message(
            websocket_api.error_message(
                msg[ID], websocket_api.const.ERR_NOT_FOUND, "OZW Node not found"
            )
        )
        return

    connection.send_result(
        msg[ID],
        {
            "metadata": node.meta_data,
            NODE_ID: node.node_id,
            OZW_INSTANCE: msg[OZW_INSTANCE],
        },
    )


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "ozw/node_statistics",
        vol.Required(NODE_ID): vol.Coerce(int),
        vol.Optional(OZW_INSTANCE, default=1): vol.Coerce(int),
    }
)
def websocket_node_statistics(hass, connection, msg):
    """Get the statistics for a Z-Wave node."""
    manager = hass.data[DOMAIN][MANAGER]
    stats = (
        manager.get_instance(msg[OZW_INSTANCE]).get_node(msg[NODE_ID]).get_statistics()
    )
    connection.send_result(
        msg[ID],
        {
            NODE_ID: msg[NODE_ID],
            "send_count": stats.send_count,
            "sent_failed": stats.sent_failed,
            "retries": stats.retries,
            "last_request_rtt": stats.last_request_rtt,
            "last_response_rtt": stats.last_response_rtt,
            "average_request_rtt": stats.average_request_rtt,
            "average_response_rtt": stats.average_response_rtt,
            "received_packets": stats.received_packets,
            "received_dup_packets": stats.received_dup_packets,
            "received_unsolicited": stats.received_unsolicited,
            OZW_INSTANCE: msg[OZW_INSTANCE],
        },
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "ozw/refresh_node_info",
        vol.Optional(OZW_INSTANCE, default=1): vol.Coerce(int),
        vol.Required(NODE_ID): vol.Coerce(int),
    }
)
def websocket_refresh_node_info(hass, connection, msg):
    """Tell OpenZWave to re-interview a node."""

    manager = hass.data[DOMAIN][MANAGER]
    options = hass.data[DOMAIN][OPTIONS]

    @callback
    def forward_node(node):
        """Forward node events to websocket."""
        if node.node_id != msg[NODE_ID]:
            return

        forward_data = {
            "type": "node_updated",
            ATTR_NODE_QUERY_STAGE: node.node_query_stage,
        }
        connection.send_message(websocket_api.event_message(msg["id"], forward_data))

    @callback
    def async_cleanup() -> None:
        """Remove signal listeners."""
        for unsub in unsubs:
            unsub()

    connection.subscriptions[msg["id"]] = async_cleanup
    unsubs = [
        options.listen(EVENT_NODE_CHANGED, forward_node),
        options.listen(EVENT_NODE_ADDED, forward_node),
    ]

    instance = manager.get_instance(msg[OZW_INSTANCE])
    instance.refresh_node(msg[NODE_ID])
    connection.send_result(msg["id"])
