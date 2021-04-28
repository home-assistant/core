"""Websocket API for Z-Wave JS."""
from __future__ import annotations

import dataclasses
from functools import wraps
import json
from typing import Callable

from aiohttp import hdrs, web, web_exceptions
import voluptuous as vol
from zwave_js_server import dump
from zwave_js_server.client import Client
from zwave_js_server.const import CommandClass, LogLevel
from zwave_js_server.exceptions import InvalidNewValue, NotFoundError, SetValueFailed
from zwave_js_server.model.log_config import LogConfig
from zwave_js_server.model.log_message import LogMessage
from zwave_js_server.util.node import async_set_config_parameter

from homeassistant.components import websocket_api
from homeassistant.components.http.view import HomeAssistantView
from homeassistant.components.websocket_api.connection import ActiveConnection
from homeassistant.components.websocket_api.const import (
    ERR_NOT_FOUND,
    ERR_NOT_SUPPORTED,
    ERR_UNKNOWN_ERROR,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import (
    CONF_DATA_COLLECTION_OPTED_IN,
    DATA_CLIENT,
    DOMAIN,
    EVENT_DEVICE_ADDED_TO_REGISTRY,
)
from .helpers import async_enable_statistics, update_data_collection_preference

# general API constants
ID = "id"
ENTRY_ID = "entry_id"
NODE_ID = "node_id"
COMMAND_CLASS_ID = "command_class_id"
TYPE = "type"
PROPERTY = "property"
PROPERTY_KEY = "property_key"
VALUE = "value"

# constants for log config commands
CONFIG = "config"
LEVEL = "level"
LOG_TO_FILE = "log_to_file"
FILENAME = "filename"
ENABLED = "enabled"
FORCE_CONSOLE = "force_console"

# constants for setting config parameters
VALUE_ID = "value_id"
STATUS = "status"

# constants for data collection
ENABLED = "enabled"
OPTED_IN = "opted_in"


def async_get_entry(orig_func: Callable) -> Callable:
    """Decorate async function to get entry."""

    @wraps(orig_func)
    async def async_get_entry_func(
        hass: HomeAssistant, connection: ActiveConnection, msg: dict
    ) -> None:
        """Provide user specific data and store to function."""
        entry_id = msg[ENTRY_ID]
        entry = hass.config_entries.async_get_entry(entry_id)
        client = hass.data[DOMAIN][entry_id][DATA_CLIENT]
        await orig_func(hass, connection, msg, entry, client)

    return async_get_entry_func


@callback
def async_register_api(hass: HomeAssistant) -> None:
    """Register all of our api endpoints."""
    websocket_api.async_register_command(hass, websocket_network_status)
    websocket_api.async_register_command(hass, websocket_node_status)
    websocket_api.async_register_command(hass, websocket_add_node)
    websocket_api.async_register_command(hass, websocket_stop_inclusion)
    websocket_api.async_register_command(hass, websocket_remove_node)
    websocket_api.async_register_command(hass, websocket_stop_exclusion)
    websocket_api.async_register_command(hass, websocket_refresh_node_info)
    websocket_api.async_register_command(hass, websocket_refresh_node_values)
    websocket_api.async_register_command(hass, websocket_refresh_node_cc_values)
    websocket_api.async_register_command(hass, websocket_subscribe_logs)
    websocket_api.async_register_command(hass, websocket_update_log_config)
    websocket_api.async_register_command(hass, websocket_get_log_config)
    websocket_api.async_register_command(hass, websocket_get_config_parameters)
    websocket_api.async_register_command(hass, websocket_set_config_parameter)
    websocket_api.async_register_command(
        hass, websocket_update_data_collection_preference
    )
    websocket_api.async_register_command(hass, websocket_data_collection_status)
    hass.http.register_view(DumpView)  # type: ignore


@websocket_api.require_admin
@websocket_api.websocket_command(
    {vol.Required(TYPE): "zwave_js/network_status", vol.Required(ENTRY_ID): str}
)
@callback
def websocket_network_status(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict
) -> None:
    """Get the status of the Z-Wave JS network."""
    entry_id = msg[ENTRY_ID]
    client = hass.data[DOMAIN][entry_id][DATA_CLIENT]
    data = {
        "client": {
            "ws_server_url": client.ws_server_url,
            "state": "connected" if client.connected else "disconnected",
            "driver_version": client.version.driver_version,
            "server_version": client.version.server_version,
        },
        "controller": {
            "home_id": client.driver.controller.data["homeId"],
            "nodes": list(client.driver.controller.nodes),
        },
    }
    connection.send_result(
        msg[ID],
        data,
    )


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/node_status",
        vol.Required(ENTRY_ID): str,
        vol.Required(NODE_ID): int,
    }
)
@callback
def websocket_node_status(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict
) -> None:
    """Get the status of a Z-Wave JS node."""
    entry_id = msg[ENTRY_ID]
    client = hass.data[DOMAIN][entry_id][DATA_CLIENT]
    node_id = msg[NODE_ID]
    node = client.driver.controller.nodes.get(node_id)

    if node is None:
        connection.send_error(msg[ID], ERR_NOT_FOUND, f"Node {node_id} not found")
        return

    data = {
        "node_id": node.node_id,
        "is_routing": node.is_routing,
        "status": node.status,
        "is_secure": node.is_secure,
        "ready": node.ready,
    }
    connection.send_result(
        msg[ID],
        data,
    )


@websocket_api.require_admin  # type: ignore
@websocket_api.async_response
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/add_node",
        vol.Required(ENTRY_ID): str,
        vol.Optional("secure", default=False): bool,
    }
)
@async_get_entry
async def websocket_add_node(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    entry: ConfigEntry,
    client: Client,
) -> None:
    """Add a node to the Z-Wave network."""
    controller = client.driver.controller
    include_non_secure = not msg["secure"]

    @callback
    def async_cleanup() -> None:
        """Remove signal listeners."""
        for unsub in unsubs:
            unsub()

    @callback
    def forward_event(event: dict) -> None:
        connection.send_message(
            websocket_api.event_message(msg[ID], {"event": event["event"]})
        )

    @callback
    def node_added(event: dict) -> None:
        node = event["node"]
        node_details = {
            "node_id": node.node_id,
            "status": node.status,
            "ready": node.ready,
        }
        connection.send_message(
            websocket_api.event_message(
                msg[ID], {"event": "node added", "node": node_details}
            )
        )

    @callback
    def device_registered(device: DeviceEntry) -> None:
        device_details = {"name": device.name, "id": device.id}
        connection.send_message(
            websocket_api.event_message(
                msg[ID], {"event": "device registered", "device": device_details}
            )
        )

    connection.subscriptions[msg["id"]] = async_cleanup
    unsubs = [
        controller.on("inclusion started", forward_event),
        controller.on("inclusion failed", forward_event),
        controller.on("inclusion stopped", forward_event),
        controller.on("node added", node_added),
        async_dispatcher_connect(
            hass, EVENT_DEVICE_ADDED_TO_REGISTRY, device_registered
        ),
    ]

    result = await controller.async_begin_inclusion(include_non_secure)
    connection.send_result(
        msg[ID],
        result,
    )


@websocket_api.require_admin  # type: ignore
@websocket_api.async_response
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/stop_inclusion",
        vol.Required(ENTRY_ID): str,
    }
)
@async_get_entry
async def websocket_stop_inclusion(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    entry: ConfigEntry,
    client: Client,
) -> None:
    """Cancel adding a node to the Z-Wave network."""
    controller = client.driver.controller
    result = await controller.async_stop_inclusion()
    connection.send_result(
        msg[ID],
        result,
    )


@websocket_api.require_admin  # type: ignore
@websocket_api.async_response
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/stop_exclusion",
        vol.Required(ENTRY_ID): str,
    }
)
@async_get_entry
async def websocket_stop_exclusion(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    entry: ConfigEntry,
    client: Client,
) -> None:
    """Cancel removing a node from the Z-Wave network."""
    controller = client.driver.controller
    result = await controller.async_stop_exclusion()
    connection.send_result(
        msg[ID],
        result,
    )


@websocket_api.require_admin  # type:ignore
@websocket_api.async_response
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/remove_node",
        vol.Required(ENTRY_ID): str,
    }
)
@async_get_entry
async def websocket_remove_node(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    entry: ConfigEntry,
    client: Client,
) -> None:
    """Remove a node from the Z-Wave network."""
    controller = client.driver.controller

    @callback
    def async_cleanup() -> None:
        """Remove signal listeners."""
        for unsub in unsubs:
            unsub()

    @callback
    def forward_event(event: dict) -> None:
        connection.send_message(
            websocket_api.event_message(msg[ID], {"event": event["event"]})
        )

    @callback
    def node_removed(event: dict) -> None:
        node = event["node"]
        node_details = {
            "node_id": node.node_id,
        }

        connection.send_message(
            websocket_api.event_message(
                msg[ID], {"event": "node removed", "node": node_details}
            )
        )

    connection.subscriptions[msg["id"]] = async_cleanup
    unsubs = [
        controller.on("exclusion started", forward_event),
        controller.on("exclusion failed", forward_event),
        controller.on("exclusion stopped", forward_event),
        controller.on("node removed", node_removed),
    ]

    result = await controller.async_begin_exclusion()
    connection.send_result(
        msg[ID],
        result,
    )


@websocket_api.require_admin  # type: ignore
@websocket_api.async_response
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/refresh_node_info",
        vol.Required(ENTRY_ID): str,
        vol.Required(NODE_ID): int,
    },
)
@async_get_entry
async def websocket_refresh_node_info(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    entry: ConfigEntry,
    client: Client,
) -> None:
    """Re-interview a node."""
    node_id = msg[NODE_ID]
    node = client.driver.controller.nodes[node_id]

    if node is None:
        connection.send_error(msg[ID], ERR_NOT_FOUND, f"Node {node_id} not found")
        return

    @callback
    def async_cleanup() -> None:
        """Remove signal listeners."""
        for unsub in unsubs:
            unsub()

    @callback
    def forward_event(event: dict) -> None:
        connection.send_message(
            websocket_api.event_message(msg[ID], {"event": event["event"]})
        )

    @callback
    def forward_stage(event: dict) -> None:
        connection.send_message(
            websocket_api.event_message(
                msg[ID], {"event": event["event"], "stage": event["stageName"]}
            )
        )

    connection.subscriptions[msg["id"]] = async_cleanup
    unsubs = [
        node.on("interview started", forward_event),
        node.on("interview completed", forward_event),
        node.on("interview stage completed", forward_stage),
        node.on("interview failed", forward_event),
    ]

    result = await node.async_refresh_info()
    connection.send_result(msg[ID], result)


@websocket_api.require_admin  # type: ignore
@websocket_api.async_response
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/refresh_node_values",
        vol.Required(ENTRY_ID): str,
        vol.Required(NODE_ID): int,
    },
)
@async_get_entry
async def websocket_refresh_node_values(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    entry: ConfigEntry,
    client: Client,
) -> None:
    """Refresh node values."""
    node_id = msg[NODE_ID]
    node = client.driver.controller.nodes[node_id]

    if node is None:
        connection.send_error(msg[ID], ERR_NOT_FOUND, f"Node {node_id} not found")
        return

    await node.async_refresh_values()
    connection.send_result(msg[ID])


@websocket_api.require_admin  # type: ignore
@websocket_api.async_response
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/refresh_node_cc_values",
        vol.Required(ENTRY_ID): str,
        vol.Required(NODE_ID): int,
        vol.Required(COMMAND_CLASS_ID): int,
    },
)
@async_get_entry
async def websocket_refresh_node_cc_values(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    entry: ConfigEntry,
    client: Client,
) -> None:
    """Refresh node values for a particular CommandClass."""
    node_id = msg[NODE_ID]
    node = client.driver.controller.nodes[node_id]

    if node is None:
        connection.send_error(msg[ID], ERR_NOT_FOUND, f"Node {node_id} not found")
        return

    command_class_id = msg[COMMAND_CLASS_ID]

    try:
        command_class = CommandClass(command_class_id)
    except ValueError:
        connection.send_error(
            msg[ID], ERR_NOT_FOUND, f"Command class {command_class_id} not found"
        )
        return

    await node.async_refresh_cc_values(command_class)
    connection.send_result(msg[ID])


@websocket_api.require_admin  # type:ignore
@websocket_api.async_response
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/set_config_parameter",
        vol.Required(ENTRY_ID): str,
        vol.Required(NODE_ID): int,
        vol.Required(PROPERTY): int,
        vol.Optional(PROPERTY_KEY): int,
        vol.Required(VALUE): int,
    }
)
@async_get_entry
async def websocket_set_config_parameter(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    entry: ConfigEntry,
    client: Client,
) -> None:
    """Set a config parameter value for a Z-Wave node."""
    node_id = msg[NODE_ID]
    property_ = msg[PROPERTY]
    property_key = msg.get(PROPERTY_KEY)
    value = msg[VALUE]
    node = client.driver.controller.nodes.get(node_id)

    if node is None:
        connection.send_error(msg[ID], ERR_NOT_FOUND, f"Node {node_id} not found")
        return

    try:
        zwave_value, cmd_status = await async_set_config_parameter(
            node, value, property_, property_key=property_key
        )
    except (InvalidNewValue, NotFoundError, NotImplementedError, SetValueFailed) as err:
        code = ERR_UNKNOWN_ERROR
        if isinstance(err, NotFoundError):
            code = ERR_NOT_FOUND
        elif isinstance(err, (InvalidNewValue, NotImplementedError)):
            code = ERR_NOT_SUPPORTED

        connection.send_error(
            msg[ID],
            code,
            str(err),
        )
        return

    connection.send_result(
        msg[ID],
        {
            VALUE_ID: zwave_value.value_id,
            STATUS: cmd_status,
        },
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/get_config_parameters",
        vol.Required(ENTRY_ID): str,
        vol.Required(NODE_ID): int,
    }
)
@callback
def websocket_get_config_parameters(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict
) -> None:
    """Get a list of configuration parameters for a Z-Wave node."""
    entry_id = msg[ENTRY_ID]
    node_id = msg[NODE_ID]
    client = hass.data[DOMAIN][entry_id][DATA_CLIENT]
    node = client.driver.controller.nodes.get(node_id)

    if node is None:
        connection.send_error(msg[ID], ERR_NOT_FOUND, f"Node {node_id} not found")
        return

    values = node.get_configuration_values()
    result = {}
    for value_id, zwave_value in values.items():
        metadata = zwave_value.metadata
        result[value_id] = {
            "property": zwave_value.property_,
            "property_key": zwave_value.property_key,
            "configuration_value_type": zwave_value.configuration_value_type.value,
            "metadata": {
                "description": metadata.description,
                "label": metadata.label,
                "type": metadata.type,
                "min": metadata.min,
                "max": metadata.max,
                "unit": metadata.unit,
                "writeable": metadata.writeable,
                "readable": metadata.readable,
            },
            "value": zwave_value.value,
        }
        if zwave_value.metadata.states:
            result[value_id]["metadata"]["states"] = zwave_value.metadata.states

    connection.send_result(
        msg[ID],
        result,
    )


def filename_is_present_if_logging_to_file(obj: dict) -> dict:
    """Validate that filename is provided if log_to_file is True."""
    if obj.get(LOG_TO_FILE, False) and FILENAME not in obj:
        raise vol.Invalid("`filename` must be provided if logging to file")
    return obj


@websocket_api.require_admin  # type: ignore
@websocket_api.async_response
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/subscribe_logs",
        vol.Required(ENTRY_ID): str,
    }
)
@async_get_entry
async def websocket_subscribe_logs(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    entry: ConfigEntry,
    client: Client,
) -> None:
    """Subscribe to log message events from the server."""
    driver = client.driver

    @callback
    def async_cleanup() -> None:
        """Remove signal listeners."""
        hass.async_create_task(driver.async_stop_listening_logs())
        unsub()

    @callback
    def forward_event(event: dict) -> None:
        log_msg: LogMessage = event["log_message"]
        connection.send_message(
            websocket_api.event_message(
                msg[ID],
                {
                    "timestamp": log_msg.timestamp,
                    "level": log_msg.level,
                    "primary_tags": log_msg.primary_tags,
                    "message": log_msg.formatted_message,
                },
            )
        )

    unsub = driver.on("logging", forward_event)
    connection.subscriptions[msg["id"]] = async_cleanup

    await driver.async_start_listening_logs()
    connection.send_result(msg[ID])


@websocket_api.require_admin  # type: ignore
@websocket_api.async_response
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/update_log_config",
        vol.Required(ENTRY_ID): str,
        vol.Required(CONFIG): vol.All(
            vol.Schema(
                {
                    vol.Optional(ENABLED): cv.boolean,
                    vol.Optional(LEVEL): vol.All(
                        cv.string,
                        vol.Lower,
                        vol.In([log_level.value for log_level in LogLevel]),
                        lambda val: LogLevel(val),  # pylint: disable=unnecessary-lambda
                    ),
                    vol.Optional(LOG_TO_FILE): cv.boolean,
                    vol.Optional(FILENAME): cv.string,
                    vol.Optional(FORCE_CONSOLE): cv.boolean,
                }
            ),
            cv.has_at_least_one_key(
                ENABLED, FILENAME, FORCE_CONSOLE, LEVEL, LOG_TO_FILE
            ),
            filename_is_present_if_logging_to_file,
        ),
    },
)
@async_get_entry
async def websocket_update_log_config(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    entry: ConfigEntry,
    client: Client,
) -> None:
    """Update the driver log config."""
    await client.driver.async_update_log_config(LogConfig(**msg[CONFIG]))
    connection.send_result(
        msg[ID],
    )


@websocket_api.require_admin  # type: ignore
@websocket_api.async_response
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/get_log_config",
        vol.Required(ENTRY_ID): str,
    },
)
@async_get_entry
async def websocket_get_log_config(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    entry: ConfigEntry,
    client: Client,
) -> None:
    """Get log configuration for the Z-Wave JS driver."""
    result = await client.driver.async_get_log_config()
    connection.send_result(
        msg[ID],
        dataclasses.asdict(result),
    )


@websocket_api.require_admin  # type: ignore
@websocket_api.async_response
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/update_data_collection_preference",
        vol.Required(ENTRY_ID): str,
        vol.Required(OPTED_IN): bool,
    },
)
@async_get_entry
async def websocket_update_data_collection_preference(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    entry: ConfigEntry,
    client: Client,
) -> None:
    """Update preference for data collection and enable/disable collection."""
    opted_in = msg[OPTED_IN]
    update_data_collection_preference(hass, entry, opted_in)

    if opted_in:
        await async_enable_statistics(client)
    else:
        await client.driver.async_disable_statistics()

    connection.send_result(
        msg[ID],
    )


@websocket_api.require_admin  # type: ignore
@websocket_api.async_response
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/data_collection_status",
        vol.Required(ENTRY_ID): str,
    },
)
@async_get_entry
async def websocket_data_collection_status(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    entry: ConfigEntry,
    client: Client,
) -> None:
    """Return data collection preference and status."""
    result = {
        OPTED_IN: entry.data.get(CONF_DATA_COLLECTION_OPTED_IN),
        ENABLED: await client.driver.async_is_statistics_enabled(),
    }
    connection.send_result(msg[ID], result)


class DumpView(HomeAssistantView):
    """View to dump the state of the Z-Wave JS server."""

    url = "/api/zwave_js/dump/{config_entry_id}"
    name = "api:zwave_js:dump"

    async def get(self, request: web.Request, config_entry_id: str) -> web.Response:
        """Dump the state of Z-Wave."""
        hass = request.app["hass"]

        if config_entry_id not in hass.data[DOMAIN]:
            raise web_exceptions.HTTPBadRequest

        entry = hass.config_entries.async_get_entry(config_entry_id)

        msgs = await dump.dump_msgs(entry.data[CONF_URL], async_get_clientsession(hass))

        return web.Response(
            body=json.dumps(msgs, indent=2) + "\n",
            headers={
                hdrs.CONTENT_TYPE: "application/json",
                hdrs.CONTENT_DISPOSITION: 'attachment; filename="zwave_js_dump.json"',
            },
        )
