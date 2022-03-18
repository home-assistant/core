"""Provides diagnostics for Z-Wave JS."""
from __future__ import annotations

from zwave_js_server.client import Client
from zwave_js_server.dump import dump_msgs
from zwave_js_server.model.node import NodeDataType

from homeassistant.components.diagnostics.util import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DATA_CLIENT, DOMAIN
from .helpers import get_home_and_node_id_from_device_entry

TO_REDACT = ["homeId", "location"]


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> list[dict]:
    """Return diagnostics for a config entry."""
    msgs: list[dict] = await dump_msgs(
        config_entry.data[CONF_URL], async_get_clientsession(hass)
    )
    return async_redact_data(msgs, TO_REDACT)


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
        "state": async_redact_data(node.data, TO_REDACT),
    }
