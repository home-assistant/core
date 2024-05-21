"""HTTP views to interact with the area registry."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.area_registry import async_get


@callback
def async_setup(hass: HomeAssistant) -> bool:
    """Enable the Area Registry views."""
    websocket_api.async_register_command(hass, websocket_list_areas)
    websocket_api.async_register_command(hass, websocket_create_area)
    websocket_api.async_register_command(hass, websocket_delete_area)
    websocket_api.async_register_command(hass, websocket_update_area)
    return True


@websocket_api.websocket_command({vol.Required("type"): "config/area_registry/list"})
@callback
def websocket_list_areas(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Handle list areas command."""
    registry = async_get(hass)
    connection.send_result(
        msg["id"],
        [entry.json_fragment for entry in registry.async_list_areas()],
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "config/area_registry/create",
        vol.Optional("aliases"): list,
        vol.Optional("floor_id"): str,
        vol.Optional("icon"): str,
        vol.Optional("labels"): [str],
        vol.Required("name"): str,
        vol.Optional("picture"): vol.Any(str, None),
    }
)
@websocket_api.require_admin
@callback
def websocket_create_area(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Create area command."""
    registry = async_get(hass)

    data = dict(msg)
    data.pop("type")
    data.pop("id")

    if "aliases" in data:
        # Convert aliases to a set
        data["aliases"] = set(data["aliases"])

    if "labels" in data:
        # Convert labels to a set
        data["labels"] = set(data["labels"])

    try:
        entry = registry.async_create(**data)
    except ValueError as err:
        connection.send_error(msg["id"], "invalid_info", str(err))
    else:
        connection.send_result(msg["id"], entry.json_fragment)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "config/area_registry/delete",
        vol.Required("area_id"): str,
    }
)
@websocket_api.require_admin
@callback
def websocket_delete_area(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Delete area command."""
    registry = async_get(hass)

    try:
        registry.async_delete(msg["area_id"])
    except KeyError:
        connection.send_error(msg["id"], "invalid_info", "Area ID doesn't exist")
    else:
        connection.send_message(websocket_api.result_message(msg["id"], "success"))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "config/area_registry/update",
        vol.Optional("aliases"): list,
        vol.Required("area_id"): str,
        vol.Optional("floor_id"): vol.Any(str, None),
        vol.Optional("icon"): vol.Any(str, None),
        vol.Optional("labels"): [str],
        vol.Optional("name"): str,
        vol.Optional("picture"): vol.Any(str, None),
    }
)
@websocket_api.require_admin
@callback
def websocket_update_area(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Handle update area websocket command."""
    registry = async_get(hass)

    data = dict(msg)
    data.pop("type")
    data.pop("id")

    if "aliases" in data:
        # Convert aliases to a set
        data["aliases"] = set(data["aliases"])

    if "labels" in data:
        # Convert labels to a set
        data["labels"] = set(data["labels"])

    try:
        entry = registry.async_update(**data)
    except ValueError as err:
        connection.send_error(msg["id"], "invalid_info", str(err))
    else:
        connection.send_result(msg["id"], entry.json_fragment)
