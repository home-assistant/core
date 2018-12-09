"""HTTP views to interact with the device registry."""
import voluptuous as vol

from homeassistant.helpers.device_registry import async_get_registry
from homeassistant.components import websocket_api

DEPENDENCIES = ['websocket_api']

WS_TYPE_LIST = 'config/device_registry/list'
SCHEMA_WS_LIST = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend({
    vol.Required('type'): WS_TYPE_LIST,
})


async def async_setup(hass):
    """Enable the Entity Registry views."""
    hass.components.websocket_api.async_register_command(
        WS_TYPE_LIST, websocket_list_devices,
        SCHEMA_WS_LIST
    )
    return True


@websocket_api.async_response
async def websocket_list_devices(hass, connection, msg):
    """Handle list devices command."""
    registry = await async_get_registry(hass)
    connection.send_message(websocket_api.result_message(
        msg['id'], [{
            'config_entries': list(entry.config_entries),
            'connections': list(entry.connections),
            'manufacturer': entry.manufacturer,
            'model': entry.model,
            'name': entry.name,
            'sw_version': entry.sw_version,
            'id': entry.id,
            'hub_device_id': entry.hub_device_id,
        } for entry in registry.devices.values()]
    ))
