"""HTTP endpoint for AI Task integration."""

from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .task import async_generate_text


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Set up the HTTP API for the conversation integration."""
    websocket_api.async_register_command(hass, websocket_generate_text)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "ai_task/generate_text",
        vol.Required("task_name"): str,
        vol.Required("entity_id"): str,
        vol.Required("instructions"): str,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def websocket_generate_text(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Run a generate text task."""
    msg.pop("type")
    msg_id = msg.pop("id")
    result = await async_generate_text(hass=hass, **msg)
    connection.send_result(msg_id, result.as_dict())
