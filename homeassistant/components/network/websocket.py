"""The Network Configuration integration websocket commands."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.websocket_api import ActiveConnection
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.network import get_url

from .const import ATTR_ADAPTERS, ATTR_CONFIGURED_ADAPTERS, NETWORK_CONFIG_SCHEMA
from .network import async_get_network


@callback
def async_register_websocket_commands(hass: HomeAssistant) -> None:
    """Register network websocket commands."""
    websocket_api.async_register_command(hass, websocket_network_adapters)
    websocket_api.async_register_command(hass, websocket_network_adapters_configure)
    websocket_api.async_register_command(hass, websocket_network_url)


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): "network"})
@websocket_api.async_response
async def websocket_network_adapters(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return network preferences."""
    network = await async_get_network(hass)
    connection.send_result(
        msg["id"],
        {
            ATTR_ADAPTERS: network.adapters,
            ATTR_CONFIGURED_ADAPTERS: network.configured_adapters,
        },
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "network/configure",
        vol.Required("config", default={}): NETWORK_CONFIG_SCHEMA,
    }
)
@websocket_api.async_response
async def websocket_network_adapters_configure(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Update network config."""
    network = await async_get_network(hass)

    await network.async_reconfig(msg["config"])

    connection.send_result(
        msg["id"],
        {ATTR_CONFIGURED_ADAPTERS: network.configured_adapters},
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "network/url",
        vol.Required("url_type"): str,
    }
)
@websocket_api.async_response
async def websocket_network_url(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Get the internal URL."""
    if msg["url_type"] not in ["internal", "external", "cloud"]:
        connection.send_error(msg["id"], "invalid_url_type", "Invalid URL type")
        return
    connection.send_result(
        msg["id"],
        get_url(
            hass,
            allow_internal=msg["url_type"] == "internal",
            allow_external=msg["url_type"] in ["external", "cloud"],
            require_cloud=msg["url_type"] == "cloud",
        ),
    )
