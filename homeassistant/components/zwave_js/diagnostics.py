"""Provides diagnostics for Z-Wave JS."""
from __future__ import annotations

from zwave_js_server.client import Client
from zwave_js_server.const import CommandClass
from zwave_js_server.dump import dump_msgs
from zwave_js_server.model.node import NodeDataType
from zwave_js_server.model.value import ValueDataType

from homeassistant.components.diagnostics.const import REDACTED
from homeassistant.components.diagnostics.util import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DATA_CLIENT, DOMAIN
from .helpers import ZwaveValueID, get_home_and_node_id_from_device_entry

KEYS_TO_REDACT = {"homeId", "location"}

VALUES_TO_REDACT = (
    ZwaveValueID(property_="userCode", command_class=CommandClass.USER_CODE),
)


def redact_value_of_zwave_value(zwave_value: ValueDataType) -> ValueDataType:
    """Redact value of a Z-Wave value."""
    for value_to_redact in VALUES_TO_REDACT:
        if (
            (
                value_to_redact.command_class is None
                or zwave_value["commandClass"] == value_to_redact.command_class
            )
            and (
                value_to_redact.property_ is None
                or zwave_value["property"] == value_to_redact.property_
            )
            and (
                value_to_redact.endpoint is None
                or zwave_value["endpoint"] == value_to_redact.endpoint
            )
            and (
                value_to_redact.property_key is None
                or zwave_value["propertyKey"] == value_to_redact.property_key
            )
        ):
            return {**zwave_value, "value": REDACTED}
    return zwave_value


def redact_node_state(node_state: NodeDataType) -> NodeDataType:
    """Redact node state."""
    return {
        **node_state,
        "values": [
            redact_value_of_zwave_value(zwave_value)
            for zwave_value in node_state["values"]
        ],
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> list[dict]:
    """Return diagnostics for a config entry."""
    msgs: list[dict] = async_redact_data(
        await dump_msgs(config_entry.data[CONF_URL], async_get_clientsession(hass)),
        KEYS_TO_REDACT,
    )
    handshake_msgs = msgs[:-1]
    network_state = msgs[-1]
    network_state["result"]["state"]["nodes"] = [
        redact_node_state(node) for node in network_state["result"]["state"]["nodes"]
    ]
    return [*handshake_msgs, network_state]


async def async_get_device_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry, device: dr.DeviceEntry
) -> NodeDataType:
    """Return diagnostics for a device."""
    client: Client = hass.data[DOMAIN][config_entry.entry_id][DATA_CLIENT]
    identifiers = get_home_and_node_id_from_device_entry(device)
    node_id = identifiers[1] if identifiers else None
    if node_id is None or node_id not in client.driver.controller.nodes:
        raise ValueError(f"Node for device {device.id} can't be found")
    node = client.driver.controller.nodes[node_id]
    return {
        "versionInfo": {
            "driverVersion": client.version.driver_version,
            "serverVersion": client.version.server_version,
            "minSchemaVersion": client.version.min_schema_version,
            "maxSchemaVersion": client.version.max_schema_version,
        },
        "state": redact_node_state(async_redact_data(node.data, KEYS_TO_REDACT)),
    }
