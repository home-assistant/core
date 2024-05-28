"""Websocket API to interact with the category registry."""

from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.websocket_api.connection import ActiveConnection
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import category_registry as cr, config_validation as cv


@callback
def async_setup(hass: HomeAssistant) -> bool:
    """Register the category registry WS commands."""
    websocket_api.async_register_command(hass, websocket_list_categories)
    websocket_api.async_register_command(hass, websocket_create_category)
    websocket_api.async_register_command(hass, websocket_delete_category)
    websocket_api.async_register_command(hass, websocket_update_category)
    return True


@websocket_api.websocket_command(
    {
        vol.Required("type"): "config/category_registry/list",
        vol.Required("scope"): str,
    }
)
@callback
def websocket_list_categories(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Handle list categories command."""
    category_registry = cr.async_get(hass)
    connection.send_result(
        msg["id"],
        [
            _entry_dict(entry)
            for entry in category_registry.async_list_categories(scope=msg["scope"])
        ],
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "config/category_registry/create",
        vol.Required("scope"): str,
        vol.Required("name"): str,
        vol.Optional("icon"): vol.Any(cv.icon, None),
    }
)
@websocket_api.require_admin
@callback
def websocket_create_category(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Create category command."""
    category_registry = cr.async_get(hass)

    data = dict(msg)
    data.pop("type")
    data.pop("id")

    try:
        entry = category_registry.async_create(**data)
    except ValueError as err:
        connection.send_error(msg["id"], "invalid_info", str(err))
    else:
        connection.send_result(msg["id"], _entry_dict(entry))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "config/category_registry/delete",
        vol.Required("scope"): str,
        vol.Required("category_id"): str,
    }
)
@websocket_api.require_admin
@callback
def websocket_delete_category(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Delete category command."""
    category_registry = cr.async_get(hass)

    try:
        category_registry.async_delete(
            scope=msg["scope"], category_id=msg["category_id"]
        )
    except KeyError:
        connection.send_error(msg["id"], "invalid_info", "Category ID doesn't exist")
    else:
        connection.send_result(msg["id"])


@websocket_api.websocket_command(
    {
        vol.Required("type"): "config/category_registry/update",
        vol.Required("scope"): str,
        vol.Required("category_id"): str,
        vol.Optional("name"): str,
        vol.Optional("icon"): vol.Any(cv.icon, None),
    }
)
@websocket_api.require_admin
@callback
def websocket_update_category(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Handle update category websocket command."""
    category_registry = cr.async_get(hass)

    data = dict(msg)
    data.pop("type")
    data.pop("id")

    try:
        entry = category_registry.async_update(**data)
    except ValueError as err:
        connection.send_error(msg["id"], "invalid_info", str(err))
    except KeyError:
        connection.send_error(msg["id"], "invalid_info", "Category ID doesn't exist")
    else:
        connection.send_result(msg["id"], _entry_dict(entry))


@callback
def _entry_dict(entry: cr.CategoryEntry) -> dict[str, Any]:
    """Convert entry to API format."""
    return {
        "category_id": entry.category_id,
        "icon": entry.icon,
        "name": entry.name,
    }
