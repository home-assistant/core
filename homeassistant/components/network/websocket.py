"""The Network Configuration integration websocket commands."""

from __future__ import annotations

from contextlib import suppress
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.websocket_api import ActiveConnection
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.network import NoURLAvailableError, get_url

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


@callback
@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "network/url",
    }
)
def websocket_network_url(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Get the internal, external, and cloud URLs."""
    internal_url = None
    external_url = None
    cloud_url = None
    with suppress(NoURLAvailableError):
        internal_url = get_url(
            hass, allow_internal=True, allow_external=False, allow_cloud=False
        )
    with suppress(NoURLAvailableError):
        external_url = get_url(
            hass, allow_internal=False, allow_external=True, prefer_external=True
        )
    with suppress(NoURLAvailableError):
        cloud_url = get_url(hass, allow_internal=False, require_cloud=True)

    connection.send_result(
        msg["id"],
        {
            "internal": internal_url,
            "external": external_url,
            "cloud": cloud_url,
        },
    )
