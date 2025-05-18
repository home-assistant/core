"""HTTP endpoint for LLM Task integration."""

from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .task import LLMTaskType, async_run_task


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Set up the HTTP API for the conversation integration."""
    websocket_api.async_register_command(hass, websocket_run_task)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "llm_task/run_task",
        vol.Required("task_name"): str,
        vol.Required("entity_id"): str,
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
    result = await async_run_task(
        hass=hass,
        task_name=msg["task_name"],
        entity_id=msg["entity_id"],
        task_type=msg["task_type"],
        prompt=msg["prompt"],
    )
    connection.send_result(msg["id"], result.as_dict())
