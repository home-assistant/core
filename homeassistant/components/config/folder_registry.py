"""Websocket API to interact with the folder registry."""
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.websocket_api.connection import ActiveConnection
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.folder_registry import FolderEntry, async_get


async def async_setup(hass: HomeAssistant) -> bool:
    """Register the folder registry WS commands."""
    websocket_api.async_register_command(hass, websocket_list_folders)
    websocket_api.async_register_command(hass, websocket_create_folder)
    websocket_api.async_register_command(hass, websocket_delete_folder)
    websocket_api.async_register_command(hass, websocket_update_folder)
    return True


@websocket_api.websocket_command(
    {
        vol.Required("type"): "config/folder_registry/list",
        vol.Required("domain"): str,
    }
)
@callback
def websocket_list_folders(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Handle list folders command."""
    registry = async_get(hass)
    connection.send_result(
        msg["id"],
        [
            _entry_dict(entry)
            for entry in registry.async_list_folders(domain=msg["domain"])
        ],
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "config/folder_registry/create",
        vol.Required("domain"): str,
        vol.Required("name"): str,
        vol.Optional("icon"): vol.Any(str, None),
    }
)
@websocket_api.require_admin
@callback
def websocket_create_folder(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Create folder command."""
    registry = async_get(hass)

    try:
        entry = registry.async_create(
            domain=msg["domain"],
            name=msg["name"],
            icon=msg.get("icon"),
        )
    except ValueError as err:
        connection.send_error(msg["id"], "invalid_info", str(err))
    else:
        connection.send_result(msg["id"], _entry_dict(entry))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "config/folder_registry/delete",
        vol.Required("folder_id"): str,
    }
)
@websocket_api.require_admin
@callback
def websocket_delete_folder(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Delete folder command."""
    registry = async_get(hass)

    try:
        registry.async_delete(msg["folder_id"])
    except KeyError:
        connection.send_error(msg["id"], "invalid_info", "Folder ID doesn't exist")
    else:
        connection.send_message(websocket_api.result_message(msg["id"], "success"))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "config/folder_registry/update",
        vol.Required("folder_id"): str,
        vol.Optional("icon"): vol.Any(str, None),
        vol.Optional("name"): str,
    }
)
@websocket_api.require_admin
@callback
def websocket_update_folder(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Handle update folder websocket command."""
    registry = async_get(hass)

    data = dict(msg)
    data.pop("type")
    data.pop("id")

    try:
        entry = registry.async_update(**data)
    except ValueError as err:
        connection.send_error(msg["id"], "invalid_info", str(err))
    else:
        connection.send_result(msg["id"], _entry_dict(entry))


@callback
def _entry_dict(entry: FolderEntry) -> dict[str, Any]:
    """Convert entry to API format."""
    return {
        "folder_id": entry.folder_id,
        "icon": entry.icon,
        "name": entry.name,
    }
