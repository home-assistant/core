"""Helpers to setup multi-factor auth module."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
import voluptuous_serialize

from homeassistant import data_entry_flow
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv

WS_TYPE_SETUP_MFA = "auth/setup_mfa"
SCHEMA_WS_SETUP_MFA = vol.All(
    websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend(
        {
            vol.Required("type"): WS_TYPE_SETUP_MFA,
            vol.Exclusive("mfa_module_id", "module_or_flow_id"): str,
            vol.Exclusive("flow_id", "module_or_flow_id"): str,
            vol.Optional("user_input"): object,
        }
    ),
    cv.has_at_least_one_key("mfa_module_id", "flow_id"),
)

WS_TYPE_DEPOSE_MFA = "auth/depose_mfa"
SCHEMA_WS_DEPOSE_MFA = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend(
    {vol.Required("type"): WS_TYPE_DEPOSE_MFA, vol.Required("mfa_module_id"): str}
)

DATA_SETUP_FLOW_MGR = "auth_mfa_setup_flow_manager"

_LOGGER = logging.getLogger(__name__)


class MfaFlowManager(data_entry_flow.FlowManager):
    """Manage multi factor authentication flows."""

    async def async_create_flow(  # type: ignore[override]
        self,
        handler_key: str,
        *,
        context: dict[str, Any],
        data: dict[str, Any],
    ) -> data_entry_flow.FlowHandler:
        """Create a setup flow. handler is a mfa module."""
        mfa_module = self.hass.auth.get_auth_mfa_module(handler_key)
        if mfa_module is None:
            raise ValueError(f"Mfa module {handler_key} is not found")

        user_id = data.pop("user_id")
        return await mfa_module.async_setup_flow(user_id)

    async def async_finish_flow(
        self, flow: data_entry_flow.FlowHandler, result: data_entry_flow.FlowResult
    ) -> data_entry_flow.FlowResult:
        """Complete an mfa setup flow.

        This method is called when a flow step returns FlowResultType.ABORT or
        FlowResultType.CREATE_ENTRY.
        """
        _LOGGER.debug("flow_result: %s", result)
        return result


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Init mfa setup flow manager."""
    hass.data[DATA_SETUP_FLOW_MGR] = MfaFlowManager(hass)

    websocket_api.async_register_command(
        hass, WS_TYPE_SETUP_MFA, websocket_setup_mfa, SCHEMA_WS_SETUP_MFA
    )

    websocket_api.async_register_command(
        hass, WS_TYPE_DEPOSE_MFA, websocket_depose_mfa, SCHEMA_WS_DEPOSE_MFA
    )


@callback
@websocket_api.ws_require_user(allow_system_user=False)
def websocket_setup_mfa(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Return a setup flow for mfa auth module."""

    async def async_setup_flow(msg: dict[str, Any]) -> None:
        """Return a setup flow for mfa auth module."""
        flow_manager: MfaFlowManager = hass.data[DATA_SETUP_FLOW_MGR]

        if (flow_id := msg.get("flow_id")) is not None:
            result = await flow_manager.async_configure(flow_id, msg.get("user_input"))
            connection.send_message(
                websocket_api.result_message(msg["id"], _prepare_result_json(result))
            )
            return

        mfa_module_id = msg["mfa_module_id"]
        if hass.auth.get_auth_mfa_module(mfa_module_id) is None:
            connection.send_message(
                websocket_api.error_message(
                    msg["id"], "no_module", f"MFA module {mfa_module_id} is not found"
                )
            )
            return

        result = await flow_manager.async_init(
            mfa_module_id, data={"user_id": connection.user.id}
        )

        connection.send_message(
            websocket_api.result_message(msg["id"], _prepare_result_json(result))
        )

    hass.async_create_task(async_setup_flow(msg))


@callback
@websocket_api.ws_require_user(allow_system_user=False)
def websocket_depose_mfa(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Remove user from mfa module."""

    async def async_depose(msg: dict[str, Any]) -> None:
        """Remove user from mfa auth module."""
        mfa_module_id = msg["mfa_module_id"]
        try:
            await hass.auth.async_disable_user_mfa(
                connection.user, msg["mfa_module_id"]
            )
        except ValueError as err:
            connection.send_message(
                websocket_api.error_message(
                    msg["id"],
                    "disable_failed",
                    f"Cannot disable MFA Module {mfa_module_id}: {err}",
                )
            )
            return

        connection.send_message(websocket_api.result_message(msg["id"], "done"))

    hass.async_create_task(async_depose(msg))


def _prepare_result_json(
    result: data_entry_flow.FlowResult,
) -> data_entry_flow.FlowResult:
    """Convert result to JSON."""
    if result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY:
        return result.copy()

    if result["type"] != data_entry_flow.FlowResultType.FORM:
        return result

    data = result.copy()

    if (schema := data["data_schema"]) is None:
        data["data_schema"] = []  # type: ignore[typeddict-item]  # json result type
    else:
        data["data_schema"] = voluptuous_serialize.convert(schema)

    return data
