"""Websocket API for automation."""
import json

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import (
    DATA_DISPATCHER,
    async_dispatcher_connect,
    async_dispatcher_send,
)
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

from .trace import (
    TraceJSONEncoder,
    get_debug_trace,
    get_debug_traces,
    get_debug_traces_for_automation,
)

# mypy: allow-untyped-calls, allow-untyped-defs


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Set up the websocket API."""
    websocket_api.async_register_command(hass, websocket_automation_trace_get)
    websocket_api.async_register_command(hass, websocket_automation_trace_list)
    websocket_api.async_register_command(hass, websocket_automation_breakpoint_clear)
    websocket_api.async_register_command(hass, websocket_automation_breakpoint_list)
    websocket_api.async_register_command(hass, websocket_automation_breakpoint_set)
    websocket_api.async_register_command(hass, websocket_automation_debug_continue)
    websocket_api.async_register_command(hass, websocket_automation_debug_step)
    websocket_api.async_register_command(hass, websocket_automation_debug_stop)
    websocket_api.async_register_command(hass, websocket_subscribe_breakpoint_events)


@callback
@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "automation/trace/get",
        vol.Required("automation_id"): str,
        vol.Required("run_id"): str,
    }
)
def websocket_automation_trace_get(hass, connection, msg):
    """Get an automation trace."""
    automation_id = msg["automation_id"]
    run_id = msg["run_id"]

    trace = get_debug_trace(hass, automation_id, run_id)
    message = websocket_api.messages.result_message(msg["id"], trace)

    connection.send_message(json.dumps(message, cls=TraceJSONEncoder, allow_nan=False))


@callback
@websocket_api.require_admin
@websocket_api.websocket_command(
    {vol.Required("type"): "automation/trace/list", vol.Optional("automation_id"): str}
)
def websocket_automation_trace_list(hass, connection, msg):
    """Summarize automation traces."""
    automation_id = msg.get("automation_id")

    if not automation_id:
        automation_traces = get_debug_traces(hass, summary=True)
    else:
        automation_traces = get_debug_traces_for_automation(
            hass, automation_id, summary=True
        )

    connection.send_result(msg["id"], automation_traces)


@callback
@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "automation/debug/breakpoint/set",
        vol.Required("automation_id"): str,
        vol.Required("node"): str,
        vol.Optional("run_id"): str,
    }
)
def websocket_automation_breakpoint_set(hass, connection, msg):
    """Set breakpoint."""
    automation_id = msg["automation_id"]
    node = msg["node"]
    run_id = msg.get("run_id")

    if (
        SCRIPT_BREAKPOINT_HIT not in hass.data.get(DATA_DISPATCHER, {})
        or not hass.data[DATA_DISPATCHER][SCRIPT_BREAKPOINT_HIT]
    ):
        raise HomeAssistantError("No breakpoint subscription")

    result = breakpoint_set(hass, automation_id, run_id, node)
    connection.send_result(msg["id"], result)


@callback
@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "automation/debug/breakpoint/clear",
        vol.Required("automation_id"): str,
        vol.Required("node"): str,
        vol.Optional("run_id"): str,
    }
)
def websocket_automation_breakpoint_clear(hass, connection, msg):
    """Clear breakpoint."""
    automation_id = msg["automation_id"]
    node = msg["node"]
    run_id = msg.get("run_id")

    result = breakpoint_clear(hass, automation_id, run_id, node)

    connection.send_result(msg["id"], result)


@callback
@websocket_api.require_admin
@websocket_api.websocket_command(
    {vol.Required("type"): "automation/debug/breakpoint/list"}
)
def websocket_automation_breakpoint_list(hass, connection, msg):
    """List breakpoints."""
    breakpoints = breakpoint_list(hass)
    for _breakpoint in breakpoints:
        _breakpoint["automation_id"] = _breakpoint.pop("unique_id")

    connection.send_result(msg["id"], breakpoints)


@callback
@websocket_api.require_admin
@websocket_api.websocket_command(
    {vol.Required("type"): "automation/debug/breakpoint/subscribe"}
)
def websocket_subscribe_breakpoint_events(hass, connection, msg):
    """Subscribe to breakpoint events."""

    @callback
    def breakpoint_hit(automation_id, run_id, node):
        """Forward events to websocket."""
        connection.send_message(
            websocket_api.event_message(
                msg["id"],
                {
                    "automation_id": automation_id,
                    "run_id": run_id,
                    "node": node,
                },
            )
        )

    remove_signal = async_dispatcher_connect(
        hass, SCRIPT_BREAKPOINT_HIT, breakpoint_hit
    )

    @callback
    def unsub():
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
        vol.Required("type"): "automation/debug/continue",
        vol.Required("automation_id"): str,
        vol.Required("run_id"): str,
    }
)
def websocket_automation_debug_continue(hass, connection, msg):
    """Resume execution of halted automation."""
    automation_id = msg["automation_id"]
    run_id = msg["run_id"]

    result = debug_continue(hass, automation_id, run_id)

    connection.send_result(msg["id"], result)


@callback
@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "automation/debug/step",
        vol.Required("automation_id"): str,
        vol.Required("run_id"): str,
    }
)
def websocket_automation_debug_step(hass, connection, msg):
    """Single step a halted automation."""
    automation_id = msg["automation_id"]
    run_id = msg["run_id"]

    result = debug_step(hass, automation_id, run_id)

    connection.send_result(msg["id"], result)


@callback
@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "automation/debug/stop",
        vol.Required("automation_id"): str,
        vol.Required("run_id"): str,
    }
)
def websocket_automation_debug_stop(hass, connection, msg):
    """Stop a halted automation."""
    automation_id = msg["automation_id"]
    run_id = msg["run_id"]

    result = debug_stop(hass, automation_id, run_id)

    connection.send_result(msg["id"], result)
