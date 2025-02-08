"""Websocket API to interact with the floor registry."""

from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.websocket_api import ActiveConnection
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import floor_registry as fr
from homeassistant.helpers.floor_registry import FloorEntry


@callback
def async_setup(hass: HomeAssistant) -> bool:
    """Register the floor registry WS commands."""
    websocket_api.async_register_command(hass, websocket_list_floors)
    websocket_api.async_register_command(hass, websocket_create_floor)
    websocket_api.async_register_command(hass, websocket_delete_floor)
    websocket_api.async_register_command(hass, websocket_update_floor)
    return True


@websocket_api.websocket_command(
    {
        vol.Required("type"): "config/floor_registry/list",
    }
)
@callback
def websocket_list_floors(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Handle list floors command."""
    registry = fr.async_get(hass)
    connection.send_result(
        msg["id"],
        [_entry_dict(entry) for entry in registry.async_list_floors()],
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "config/floor_registry/create",
        vol.Required("name"): str,
        vol.Optional("aliases"): list,
        vol.Optional("icon"): vol.Any(str, None),
        vol.Optional("level"): vol.Any(int, None),
    }
)
@websocket_api.require_admin
@callback
def websocket_create_floor(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Create floor command."""
    registry = fr.async_get(hass)

    data = dict(msg)
    data.pop("type")
    data.pop("id")

    if "aliases" in data:
        # Convert aliases to a set
        data["aliases"] = set(data["aliases"])

    try:
        entry = registry.async_create(**data)
    except ValueError as err:
        connection.send_error(msg["id"], "invalid_info", str(err))
    else:
        connection.send_result(msg["id"], _entry_dict(entry))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "config/floor_registry/delete",
        vol.Required("floor_id"): str,
    }
)
@websocket_api.require_admin
@callback
def websocket_delete_floor(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Delete floor command."""
    registry = fr.async_get(hass)

    try:
        registry.async_delete(msg["floor_id"])
    except KeyError:
        connection.send_error(msg["id"], "invalid_info", "Floor ID doesn't exist")
    else:
        connection.send_result(msg["id"])


@websocket_api.websocket_command(
    {
        vol.Required("type"): "config/floor_registry/update",
        vol.Required("floor_id"): str,
        vol.Optional("aliases"): list,
        vol.Optional("icon"): vol.Any(str, None),
        vol.Optional("level"): vol.Any(int, None),
        vol.Optional("name"): str,
    }
)
@websocket_api.require_admin
@callback
def websocket_update_floor(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Handle update floor websocket command."""
    registry = fr.async_get(hass)

    data = dict(msg)
    data.pop("type")
    data.pop("id")

    if "aliases" in data:
        # Convert aliases to a set
        data["aliases"] = set(data["aliases"])

    try:
        entry = registry.async_update(**data)
    except ValueError as err:
        connection.send_error(msg["id"], "invalid_info", str(err))
    else:
        connection.send_result(msg["id"], _entry_dict(entry))


@callback
def _entry_dict(entry: FloorEntry) -> dict[str, Any]:
    """Convert entry to API format."""
    return {
        "aliases": list(entry.aliases),
        "created_at": entry.created_at.timestamp(),
        "floor_id": entry.floor_id,
        "icon": entry.icon,
        "level": entry.level,
        "name": entry.name,
        "modified_at": entry.modified_at.timestamp(),
    }
