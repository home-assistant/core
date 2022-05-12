"""HTTP views to interact with the area registry."""
import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import callback
from homeassistant.helpers.area_registry import async_get


async def async_setup(hass):
    """Enable the Area Registry views."""
    websocket_api.async_register_command(hass, websocket_list_areas)
    websocket_api.async_register_command(hass, websocket_create_area)
    websocket_api.async_register_command(hass, websocket_delete_area)
    websocket_api.async_register_command(hass, websocket_update_area)
    return True


@websocket_api.websocket_command({vol.Required("type"): "config/area_registry/list"})
@callback
def websocket_list_areas(hass, connection, msg):
    """Handle list areas command."""
    registry = async_get(hass)
    connection.send_result(
        msg["id"],
        [_entry_dict(entry) for entry in registry.async_list_areas()],
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "config/area_registry/create",
        vol.Required("name"): str,
        vol.Optional("picture"): vol.Any(str, None),
    }
)
@websocket_api.require_admin
@callback
def websocket_create_area(hass, connection, msg):
    """Create area command."""
    registry = async_get(hass)

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
        vol.Required("type"): "config/area_registry/delete",
        vol.Required("area_id"): str,
    }
)
@websocket_api.require_admin
@callback
def websocket_delete_area(hass, connection, msg):
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
        vol.Required("area_id"): str,
        vol.Optional("name"): str,
        vol.Optional("picture"): vol.Any(str, None),
    }
)
@websocket_api.require_admin
@callback
def websocket_update_area(hass, connection, msg):
    """Handle update area websocket command."""
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
def _entry_dict(entry):
    """Convert entry to API format."""
    return {"area_id": entry.id, "name": entry.name, "picture": entry.picture}
