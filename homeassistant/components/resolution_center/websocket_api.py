"""The resolution center websocket API."""
from __future__ import annotations

import dataclasses
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .issue_handler import async_dismiss_issue
from .issue_registry import async_get as async_get_issue_registry


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Set up the resolution center websocket API."""
    websocket_api.async_register_command(hass, ws_dismiss_issue)
    websocket_api.async_register_command(hass, ws_list_issues)


@callback
@websocket_api.websocket_command(
    {
        vol.Required("type"): "resolution_center/dismiss_issue",
        vol.Required("domain"): str,
        vol.Required("issue_id"): str,
    }
)
def ws_dismiss_issue(
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

    def ws_dict(kv_pairs: list[tuple[Any, Any]]) -> dict[Any, Any]:
        result = {k: v for k, v in kv_pairs if k != "active"}
        result["dismissed"] = result["dismissed_version"] is not None
        return result

    issue_registry = async_get_issue_registry(hass)
    issues = [
        dataclasses.asdict(issue, dict_factory=ws_dict)
        for issue in issue_registry.issues.values()
    ]

    connection.send_result(msg["id"], {"issues": issues})
