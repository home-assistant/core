"""The resolution center websocket API."""
from __future__ import annotations

import dataclasses

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN
from .resolution_center import async_dismiss_issue


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Set up the resolution center websocket API."""
    websocket_api.async_register_command(hass, ws_dismiss_issue)
    websocket_api.async_register_command(hass, ws_list_issues)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "resolution_center/dismiss_issue",
        vol.Required("domain"): str,
        vol.Required("issue_id"): str,
    }
)
@websocket_api.async_response
async def ws_dismiss_issue(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Fix an issue."""
    async_dismiss_issue(hass, msg["domain"], msg["issue_id"])

    connection.send_result(msg["id"])


@websocket_api.websocket_command(
    {
        vol.Required("type"): "resolution_center/list_issues",
    }
)
@callback
def ws_list_issues(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Return a list of issues."""
    issues = [
        dataclasses.asdict(issue) for issue in hass.data[DOMAIN]["issues"].values()
    ]

    connection.send_result(msg["id"], {"issues": issues})
