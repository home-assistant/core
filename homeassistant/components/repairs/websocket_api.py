"""The repairs websocket API."""
from __future__ import annotations

import dataclasses
from http import HTTPStatus
from typing import Any

from aiohttp import web
import voluptuous as vol

from homeassistant import data_entry_flow
from homeassistant.auth.permissions.const import POLICY_EDIT
from homeassistant.components import websocket_api
from homeassistant.components.http.data_validator import RequestDataValidator
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import Unauthorized
from homeassistant.helpers.data_entry_flow import (
    FlowManagerIndexView,
    FlowManagerResourceView,
)
from homeassistant.helpers.issue_registry import (
    async_get as async_get_issue_registry,
    async_ignore_issue,
)

from .const import DOMAIN


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Set up the repairs websocket API."""
    websocket_api.async_register_command(hass, ws_ignore_issue)
    websocket_api.async_register_command(hass, ws_list_issues)

    hass.http.register_view(RepairsFlowIndexView(hass.data[DOMAIN]["flow_manager"]))
    hass.http.register_view(RepairsFlowResourceView(hass.data[DOMAIN]["flow_manager"]))


@callback
@websocket_api.websocket_command(
    {
        vol.Required("type"): "repairs/ignore_issue",
        vol.Required("domain"): str,
        vol.Required("issue_id"): str,
        vol.Required("ignore"): bool,
    }
)
def ws_ignore_issue(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Fix an issue."""
    async_ignore_issue(hass, msg["domain"], msg["issue_id"], msg["ignore"])

    connection.send_result(msg["id"])


@websocket_api.websocket_command(
    {
        vol.Required("type"): "repairs/list_issues",
    }
)
@callback
def ws_list_issues(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Return a list of issues."""

    def ws_dict(kv_pairs: list[tuple[Any, Any]]) -> dict[Any, Any]:
        excluded_keys = ("active", "data", "is_persistent")
        result = {k: v for k, v in kv_pairs if k not in excluded_keys}
        result["ignored"] = result["dismissed_version"] is not None
        result["created"] = result["created"].isoformat()
        return result

    issue_registry = async_get_issue_registry(hass)
    issues = [
        dataclasses.asdict(issue, dict_factory=ws_dict)
        for issue in issue_registry.issues.values()
        if issue.active
    ]

    connection.send_result(msg["id"], {"issues": issues})


class RepairsFlowIndexView(FlowManagerIndexView):
    """View to create issue fix flows."""

    url = "/api/repairs/issues/fix"
    name = "api:repairs:issues:fix"

    @RequestDataValidator(
        vol.Schema(
            {
                vol.Required("handler"): str,
                vol.Required("issue_id"): str,
            },
            extra=vol.ALLOW_EXTRA,
        )
    )
    async def post(self, request: web.Request, data: dict[str, Any]) -> web.Response:
        """Handle a POST request."""
        if not request["hass_user"].is_admin:
            raise Unauthorized(permission=POLICY_EDIT)

        try:
            result = await self._flow_mgr.async_init(
                data["handler"],
                data={"issue_id": data["issue_id"]},
            )
        except data_entry_flow.UnknownHandler:
            return self.json_message("Invalid handler specified", HTTPStatus.NOT_FOUND)
        except data_entry_flow.UnknownStep:
            return self.json_message(
                "Handler does not support user", HTTPStatus.BAD_REQUEST
            )

        result = self._prepare_result_json(result)

        return self.json(result)


class RepairsFlowResourceView(FlowManagerResourceView):
    """View to interact with the option flow manager."""

    url = "/api/repairs/issues/fix/{flow_id}"
    name = "api:repairs:issues:fix:resource"

    async def get(self, request: web.Request, flow_id: str) -> web.Response:
        """Get the current state of a data_entry_flow."""
        if not request["hass_user"].is_admin:
            raise Unauthorized(permission=POLICY_EDIT)

        return await super().get(request, flow_id)

    # pylint: disable=arguments-differ
    async def post(self, request: web.Request, flow_id: str) -> web.Response:
        """Handle a POST request."""
        if not request["hass_user"].is_admin:
            raise Unauthorized(permission=POLICY_EDIT)

        # pylint: disable=no-value-for-parameter
        return await super().post(request, flow_id)
