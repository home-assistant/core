"""WebSocket API for the Entity Migration integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback, valid_entity_id

from .scanner import EntityMigrationScanner

if TYPE_CHECKING:
    from .models import ScanResult


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Set up the entity migration WebSocket API."""
    websocket_api.async_register_command(hass, websocket_scan)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "entity_migration/scan",
        vol.Required("entity_id"): str,
    }
)
@websocket_api.async_response
async def websocket_scan(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Handle entity_migration/scan WebSocket command.

    Scans for all references to the specified entity across configurations.
    """
    entity_id = msg["entity_id"]

    # Validate entity_id format
    if not valid_entity_id(entity_id):
        connection.send_error(
            msg["id"],
            "invalid_entity_id",
            f"Invalid entity ID format: {entity_id}",
        )
        return

    scanner = EntityMigrationScanner(hass)

    # Scanner internally handles all scan errors gracefully,
    # so no exception catching needed here
    result: ScanResult = await scanner.async_scan(entity_id)

    connection.send_result(msg["id"], result.as_dict())
