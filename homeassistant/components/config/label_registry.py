"""Websocket API to interact with the label registry."""

from typing import Any

import probatio

from homeassistant.components import websocket_api
from homeassistant.components.websocket_api import ActiveConnection
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, label_registry as lr
from homeassistant.helpers.label_registry import LabelEntry

SUPPORTED_LABEL_THEME_COLORS = {
    "primary",
    "accent",
    "disabled",
    "red",
    "pink",
    "purple",
    "deep-purple",
    "indigo",
    "blue",
    "light-blue",
    "cyan",
    "teal",
    "green",
    "light-green",
    "lime",
    "yellow",
    "amber",
    "orange",
    "deep-orange",
    "brown",
    "light-grey",
    "grey",
    "dark-grey",
    "blue-grey",
    "black",
    "white",
}


@callback
def async_setup(hass: HomeAssistant) -> bool:
    """Register the Label Registry WS commands."""
    websocket_api.async_register_command(hass, websocket_list_labels)
    websocket_api.async_register_command(hass, websocket_create_label)
    websocket_api.async_register_command(hass, websocket_delete_label)
    websocket_api.async_register_command(hass, websocket_update_label)
    return True


@websocket_api.websocket_command(
    {
        probatio.Required("type"): "config/label_registry/list",
    }
)
@callback
def websocket_list_labels(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Handle list labels command."""
    registry = lr.async_get(hass)
    connection.send_result(
        msg["id"],
        [_entry_dict(entry) for entry in registry.async_list_labels()],
    )


@websocket_api.websocket_command(
    {
        probatio.Required("type"): "config/label_registry/create",
        probatio.Required("name"): str,
        probatio.Optional("color"): probatio.Any(
            cv.color_hex, probatio.In(SUPPORTED_LABEL_THEME_COLORS), None
        ),
        probatio.Optional("description"): probatio.Any(str, None),
        probatio.Optional("icon"): probatio.Any(cv.icon, None),
    }
)
@websocket_api.require_admin
@callback
def websocket_create_label(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Create label command."""
    registry = lr.async_get(hass)

    data = dict(msg)
    data.pop("type")
    data.pop("id")

    try:
        entry = registry.async_create(**data)
    except ValueError as err:
        connection.send_error(msg["id"], "invalid_info", str(err))
    else:
        connection.send_result(msg["id"], _entry_dict(entry))


@websocket_api.websocket_command(
    {
        probatio.Required("type"): "config/label_registry/delete",
        probatio.Required("label_id"): str,
    }
)
@websocket_api.require_admin
@callback
def websocket_delete_label(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Delete label command."""
    registry = lr.async_get(hass)

    try:
        registry.async_delete(msg["label_id"])
    except KeyError:
        connection.send_error(msg["id"], "invalid_info", "Label ID doesn't exist")
    else:
        connection.send_result(msg["id"])


@websocket_api.websocket_command(
    {
        probatio.Required("type"): "config/label_registry/update",
        probatio.Required("label_id"): str,
        probatio.Optional("color"): probatio.Any(
            cv.color_hex, probatio.In(SUPPORTED_LABEL_THEME_COLORS), None
        ),
        probatio.Optional("description"): probatio.Any(str, None),
        probatio.Optional("icon"): probatio.Any(cv.icon, None),
        probatio.Optional("name"): str,
    }
)
@websocket_api.require_admin
@callback
def websocket_update_label(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Handle update label websocket command."""
    registry = lr.async_get(hass)

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
def _entry_dict(entry: LabelEntry) -> dict[str, Any]:
    """Convert entry to API format."""
    return {
        "color": entry.color,
        "created_at": entry.created_at.timestamp(),
        "description": entry.description,
        "icon": entry.icon,
        "label_id": entry.label_id,
        "name": entry.name,
        "modified_at": entry.modified_at.timestamp(),
    }
