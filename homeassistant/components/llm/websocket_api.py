"""Websocket API for the LLM integration."""

from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.llm import async_get_apis


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Set up the LLM websocket API."""
    websocket_api.async_register_command(hass, websocket_list_apis)


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): "llm/api/list"})
@callback
def websocket_list_apis(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """List the registered LLM APIs.

    Each API is described by the ID used to select it and the name shown to
    the user. APIs are listed in registration order.
    """
    connection.send_result(
        msg["id"],
        {"apis": [{"id": api.id, "name": api.name} for api in async_get_apis(hass)]},
    )
