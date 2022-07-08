"""The resolution center websocket API."""
from __future__ import annotations

import dataclasses
from typing import Any

import voluptuous as vol
import voluptuous_serialize

from homeassistant import data_entry_flow
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN
from .issue_handler import ResolutionCenterFlowManager, async_dismiss_issue
from .issue_registry import async_get as async_get_issue_registry


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Set up the resolution center websocket API."""
    websocket_api.async_register_command(hass, ws_dismiss_issue)
    websocket_api.async_register_command(hass, ws_fix_issue)
    websocket_api.async_register_command(hass, ws_fix_issue_confirm)
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
        vol.Required("type"): "resolution_center/fix_issue",
        vol.Required("domain"): str,
        vol.Required("issue_id"): str,
    }
)
@websocket_api.async_response
async def ws_fix_issue(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Start a flow to an issue."""
    flow_manager: ResolutionCenterFlowManager = hass.data[DOMAIN]["flow_manager"]
    result = await flow_manager.async_init(
        msg["domain"], data={"issue_id": msg["issue_id"]}
    )
    connection.send_message(
        websocket_api.result_message(msg["id"], _prepare_result_json(result))
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "resolution_center/fix_issue_confirm",
        vol.Required("flow_id"): str,
        vol.Optional("user_input"): dict,
    }
)
@websocket_api.async_response
async def ws_fix_issue_confirm(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Provide user input for an issue fix flow."""
    flow_manager: ResolutionCenterFlowManager = hass.data[DOMAIN]["flow_manager"]
    result = await flow_manager.async_configure(msg["flow_id"], msg.get("user_input"))
    connection.send_message(
        websocket_api.result_message(msg["id"], _prepare_result_json(result))
    )


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


def _prepare_result_json(
    result: data_entry_flow.FlowResult,
) -> data_entry_flow.FlowResult:
    """Convert issue flow result to ensure it can be JSON serialized."""
    data = result.copy()

    if data["type"] != data_entry_flow.FlowResultType.FORM:
        return data

    schema = data["data_schema"]
    data["data_schema"] = voluptuous_serialize.convert(schema) if schema else []

    return data
