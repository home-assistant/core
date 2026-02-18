"""Websocket commands for the Vacuum integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.websocket_api import ERR_NOT_FOUND, ERR_NOT_SUPPORTED
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv

from .const import DATA_COMPONENT, VacuumEntityFeature


@callback
def async_register_websocket_handlers(hass: HomeAssistant) -> None:
    """Register websocket commands."""
    websocket_api.async_register_command(hass, handle_get_segments)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "vacuum/get_segments",
        vol.Required("entity_id"): cv.strict_entity_id,
    }
)
@websocket_api.async_response
async def handle_get_segments(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Get segments for a vacuum."""
    entity_id = msg["entity_id"]
    entity = hass.data[DATA_COMPONENT].get_entity(entity_id)
    if entity is None:
        connection.send_error(msg["id"], ERR_NOT_FOUND, f"Entity {entity_id} not found")
        return

    if VacuumEntityFeature.CLEAN_AREA not in entity.supported_features:
        connection.send_error(
            msg["id"], ERR_NOT_SUPPORTED, f"Entity {entity_id} not supported"
        )
        return

    segments = await entity.async_get_segments()

    connection.send_result(msg["id"], {"segments": segments})
