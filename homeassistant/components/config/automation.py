"""Provide configuration end points for Automations."""
from collections import OrderedDict
import uuid

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.automation import (
    get_debug_traces,
    get_debug_traces_for_automation,
)
from homeassistant.components.automation.config import (
    DOMAIN,
    PLATFORM_SCHEMA,
    async_validate_config_item,
)
from homeassistant.config import AUTOMATION_CONFIG_PATH
from homeassistant.const import CONF_ID, SERVICE_RELOAD
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, entity_registry
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

from . import ACTION_DELETE, EditIdBasedConfigView


async def async_setup(hass):
    """Set up the Automation config API."""

    websocket_api.async_register_command(hass, websocket_automation_trace_get)
    websocket_api.async_register_command(hass, websocket_automation_trace_list)
    websocket_api.async_register_command(hass, websocket_automation_breakpoint_clear)
    websocket_api.async_register_command(hass, websocket_automation_breakpoint_list)
    websocket_api.async_register_command(hass, websocket_automation_breakpoint_set)
    websocket_api.async_register_command(hass, websocket_automation_debug_continue)
    websocket_api.async_register_command(hass, websocket_automation_debug_step)
    websocket_api.async_register_command(hass, websocket_automation_debug_stop)
    websocket_api.async_register_command(hass, websocket_subscribe_breakpoint_events)

    async def hook(action, config_key):
        """post_write_hook for Config View that reloads automations."""
        await hass.services.async_call(DOMAIN, SERVICE_RELOAD)

        if action != ACTION_DELETE:
            return

        ent_reg = await entity_registry.async_get_registry(hass)

        entity_id = ent_reg.async_get_entity_id(DOMAIN, DOMAIN, config_key)

        if entity_id is None:
            return

        ent_reg.async_remove(entity_id)

    hass.http.register_view(
        EditAutomationConfigView(
            DOMAIN,
            "config",
            AUTOMATION_CONFIG_PATH,
            cv.string,
            PLATFORM_SCHEMA,
            post_write_hook=hook,
            data_validator=async_validate_config_item,
        )
    )
    return True


class EditAutomationConfigView(EditIdBasedConfigView):
    """Edit automation config."""

    def _write_value(self, hass, data, config_key, new_value):
        """Set value."""
        index = None
        for index, cur_value in enumerate(data):
            # When people copy paste their automations to the config file,
            # they sometimes forget to add IDs. Fix it here.
            if CONF_ID not in cur_value:
                cur_value[CONF_ID] = uuid.uuid4().hex

            elif cur_value[CONF_ID] == config_key:
                break
        else:
            cur_value = OrderedDict()
            cur_value[CONF_ID] = config_key
            index = len(data)
            data.append(cur_value)

        # Iterate through some keys that we want to have ordered in the output
        updated_value = OrderedDict()
        for key in ("id", "alias", "description", "trigger", "condition", "action"):
            if key in cur_value:
                updated_value[key] = cur_value[key]
            if key in new_value:
                updated_value[key] = new_value[key]

        # We cover all current fields above, but just in case we start
        # supporting more fields in the future.
        updated_value.update(cur_value)
        updated_value.update(new_value)
        data[index] = updated_value


@callback
@websocket_api.require_admin
@websocket_api.websocket_command(
    {vol.Required("type"): "automation/trace/get", vol.Optional("automation_id"): str}
)
def websocket_automation_trace_get(hass, connection, msg):
    """Get automation traces."""
    automation_id = msg.get("automation_id")

    if not automation_id:
        automation_traces = get_debug_traces(hass)
    else:
        automation_traces = {
            automation_id: get_debug_traces_for_automation(hass, automation_id)
        }

    connection.send_result(msg["id"], automation_traces)


@callback
@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): "automation/trace/list"})
def websocket_automation_trace_list(hass, connection, msg):
    """Summarize automation traces."""
    automation_traces = get_debug_traces(hass, summary=True)

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
