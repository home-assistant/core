"""HTTP endpoint for AI Task integration."""

from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .const import DATA_PREFERENCES


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Set up the HTTP API for the conversation integration."""
    websocket_api.async_register_command(hass, websocket_get_preferences)
    websocket_api.async_register_command(hass, websocket_set_preferences)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "ai_task/preferences/get",
    }
)
@callback
def websocket_get_preferences(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Get AI task preferences."""
    preferences = hass.data[DATA_PREFERENCES]
    connection.send_result(msg["id"], preferences.as_dict())


@websocket_api.websocket_command(
    {
        vol.Required("type"): "ai_task/preferences/set",
        vol.Optional("gen_data_entity_id"): vol.Any(str, None),
    }
)
@websocket_api.require_admin
@callback
def websocket_set_preferences(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Set AI task preferences."""
    preferences = hass.data[DATA_PREFERENCES]
    msg.pop("type")
    msg_id = msg.pop("id")
    preferences.async_set_preferences(**msg)
    connection.send_result(msg_id, preferences.as_dict())
