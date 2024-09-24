"""Websocket API for automation."""

import json
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import (
    DATA_DISPATCHER,
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.json import ExtendedJSONEncoder
from homeassistant.helpers.script import (
    SCRIPT_BREAKPOINT_HIT,
    SCRIPT_DEBUG_CONTINUE_ALL,
    breakpoint_clear,
    breakpoint_clear_all,
    breakpoint_list,
    breakpoint_set,
    debug_continue,
    debug_step,
    debug_stop,
)

from .. import trace  # noqa: TID252 (see PR 125822)

TRACE_DOMAINS = ("automation", "script")


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Set up the websocket API."""
    websocket_api.async_register_command(hass, websocket_trace_get)
    websocket_api.async_register_command(hass, websocket_trace_list)
    websocket_api.async_register_command(hass, websocket_trace_contexts)
    websocket_api.async_register_command(hass, websocket_breakpoint_clear)
    websocket_api.async_register_command(hass, websocket_breakpoint_list)
    websocket_api.async_register_command(hass, websocket_breakpoint_set)
    websocket_api.async_register_command(hass, websocket_debug_continue)
    websocket_api.async_register_command(hass, websocket_debug_step)
    websocket_api.async_register_command(hass, websocket_debug_stop)
    websocket_api.async_register_command(hass, websocket_subscribe_breakpoint_events)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "trace/get",
        vol.Required("domain"): vol.In(TRACE_DOMAINS),
        vol.Required("item_id"): str,
        vol.Required("run_id"): str,
    }
)
@websocket_api.async_response
async def websocket_trace_get(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Get a script or automation trace."""
    key = f"{msg['domain']}.{msg['item_id']}"
    run_id = msg["run_id"]

    try:
        requested_trace = await trace.async_get_trace(hass, key, run_id)
    except KeyError:
        connection.send_error(
            msg["id"], websocket_api.ERR_NOT_FOUND, "The trace could not be found"
        )
        return

    message = websocket_api.messages.result_message(msg["id"], requested_trace)

    connection.send_message(
        json.dumps(message, cls=ExtendedJSONEncoder, allow_nan=False)
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "trace/list",
        vol.Required("domain", "id"): vol.In(TRACE_DOMAINS),
        vol.Optional("item_id", "id"): str,
    }
)
@websocket_api.async_response
async def websocket_trace_list(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Summarize script and automation traces."""
    wanted_domain = msg["domain"]
    key = f"{msg['domain']}.{msg['item_id']}" if "item_id" in msg else None

    traces = await trace.async_list_traces(hass, wanted_domain, key)

    connection.send_result(msg["id"], traces)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "trace/contexts",
        vol.Inclusive("domain", "id"): vol.In(TRACE_DOMAINS),
        vol.Inclusive("item_id", "id"): str,
    }
)
@websocket_api.async_response
async def websocket_trace_contexts(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Retrieve contexts we have traces for."""
    key = f"{msg['domain']}.{msg['item_id']}" if "item_id" in msg else None

    contexts = await trace.async_list_contexts(hass, key)

    connection.send_result(msg["id"], contexts)


@callback
@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "trace/debug/breakpoint/set",
        vol.Required("domain"): vol.In(TRACE_DOMAINS),
        vol.Required("item_id"): str,
        vol.Required("node"): str,
        vol.Optional("run_id"): str,
    }
)
def websocket_breakpoint_set(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Set breakpoint."""
    key = f"{msg['domain']}.{msg['item_id']}"
    node: str = msg["node"]
    run_id: str | None = msg.get("run_id")

    if (
        SCRIPT_BREAKPOINT_HIT not in hass.data.get(DATA_DISPATCHER, {})
        or not hass.data[DATA_DISPATCHER][SCRIPT_BREAKPOINT_HIT]
    ):
        raise HomeAssistantError("No breakpoint subscription")

    result = breakpoint_set(hass, key, run_id, node)
    connection.send_result(msg["id"], result)


@callback
@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "trace/debug/breakpoint/clear",
        vol.Required("domain"): vol.In(TRACE_DOMAINS),
        vol.Required("item_id"): str,
        vol.Required("node"): str,
        vol.Optional("run_id"): str,
    }
)
def websocket_breakpoint_clear(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Clear breakpoint."""
    key = f"{msg['domain']}.{msg['item_id']}"
    node: str = msg["node"]
    run_id: str | None = msg.get("run_id")

    result = breakpoint_clear(hass, key, run_id, node)

    connection.send_result(msg["id"], result)


@callback
@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): "trace/debug/breakpoint/list"})
def websocket_breakpoint_list(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """List breakpoints."""
    breakpoints = breakpoint_list(hass)
    for _breakpoint in breakpoints:
        key = _breakpoint.pop("key")
        _breakpoint["domain"], _breakpoint["item_id"] = key.split(".", 1)

    connection.send_result(msg["id"], breakpoints)


@callback
@websocket_api.require_admin
@websocket_api.websocket_command(
    {vol.Required("type"): "trace/debug/breakpoint/subscribe"}
)
def websocket_subscribe_breakpoint_events(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Subscribe to breakpoint events."""

    @callback
    def breakpoint_hit(key: str, run_id: str, node: str) -> None:
        """Forward events to websocket."""
        domain, item_id = key.split(".", 1)
        connection.send_message(
            websocket_api.event_message(
                msg["id"],
                {
                    "domain": domain,
                    "item_id": item_id,
                    "run_id": run_id,
                    "node": node,
                },
            )
        )

    remove_signal = async_dispatcher_connect(
        hass, SCRIPT_BREAKPOINT_HIT, breakpoint_hit
    )

    @callback
    def unsub() -> None:
        """Unsubscribe from breakpoint events."""
        remove_signal()
        if (
            SCRIPT_BREAKPOINT_HIT not in hass.data.get(DATA_DISPATCHER, {})
            or not hass.data[DATA_DISPATCHER][SCRIPT_BREAKPOINT_HIT]
        ):
            breakpoint_clear_all(hass)
            async_dispatcher_send(hass, SCRIPT_DEBUG_CONTINUE_ALL)

    connection.subscriptions[msg["id"]] = unsub

    connection.send_message(websocket_api.result_message(msg["id"]))


@callback
@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "trace/debug/continue",
        vol.Required("domain"): vol.In(TRACE_DOMAINS),
        vol.Required("item_id"): str,
        vol.Required("run_id"): str,
    }
)
def websocket_debug_continue(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Resume execution of halted script or automation."""
    key = f"{msg['domain']}.{msg['item_id']}"
    run_id: str = msg["run_id"]

    result = debug_continue(hass, key, run_id)

    connection.send_result(msg["id"], result)


@callback
@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "trace/debug/step",
        vol.Required("domain"): vol.In(TRACE_DOMAINS),
        vol.Required("item_id"): str,
        vol.Required("run_id"): str,
    }
)
def websocket_debug_step(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Single step a halted script or automation."""
    key = f"{msg['domain']}.{msg['item_id']}"
    run_id: str = msg["run_id"]

    result = debug_step(hass, key, run_id)

    connection.send_result(msg["id"], result)


@callback
@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "trace/debug/stop",
        vol.Required("domain"): vol.In(TRACE_DOMAINS),
        vol.Required("item_id"): str,
        vol.Required("run_id"): str,
    }
)
def websocket_debug_stop(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Stop a halted script or automation."""
    key = f"{msg['domain']}.{msg['item_id']}"
    run_id: str = msg["run_id"]

    result = debug_stop(hass, key, run_id)

    connection.send_result(msg["id"], result)
