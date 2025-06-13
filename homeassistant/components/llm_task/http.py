"""HTTP endpoint for LLM Task integration."""

from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .const import DATA_PREFERENCES
from .task import LLMTaskType, async_run_task


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Set up the HTTP API for the conversation integration."""
    websocket_api.async_register_command(hass, websocket_run_task)
    websocket_api.async_register_command(hass, websocket_get_preferences)
    websocket_api.async_register_command(hass, websocket_set_preferences)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "llm_task/run_task",
        vol.Required("task_name"): str,
        vol.Optional("entity_id"): str,
        vol.Required("task_type"): (lambda v: LLMTaskType(v)),  # pylint: disable=unnecessary-lambda
        vol.Required("prompt"): str,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def websocket_run_task(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Run an LLM task."""
    msg.pop("type")
    msg_id = msg.pop("id")
    result = await async_run_task(hass=hass, **msg)
    connection.send_result(msg_id, result.as_dict())


@websocket_api.websocket_command(
    {
        vol.Required("type"): "llm_task/preferences/get",
    }
)
@callback
def websocket_get_preferences(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Get LLM task preferences."""
    preferences = hass.data[DATA_PREFERENCES]
    connection.send_result(msg["id"], preferences.as_dict())


@websocket_api.websocket_command(
    {
        vol.Required("type"): "llm_task/preferences/set",
        vol.Optional("summary_entity_id"): vol.Any(str, None),
        vol.Optional("generate_entity_id"): vol.Any(str, None),
    }
)
@websocket_api.require_admin
@callback
def websocket_set_preferences(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Set LLM task preferences."""
    preferences = hass.data[DATA_PREFERENCES]
    msg.pop("type")
    msg_id = msg.pop("id")
    preferences.async_set_preferences(**msg)
    connection.send_result(msg_id, preferences.as_dict())
