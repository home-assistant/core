"""Insteon API interface for the frontend."""

from homeassistant.components import websocket_api
from homeassistant.core import callback

from .aldb import (
    websocket_add_default_links,
    websocket_change_aldb_record,
    websocket_create_aldb_record,
    websocket_get_aldb,
    websocket_load_aldb,
    websocket_notify_on_aldb_status,
    websocket_reset_aldb,
    websocket_write_aldb,
)
from .device import websocket_get_device
from .properties import (
    websocket_change_properties_record,
    websocket_get_properties,
    websocket_load_properties,
    websocket_reset_properties,
    websocket_write_properties,
)


@callback
def async_load_api(hass):
    """Set up the web socket API."""
    websocket_api.async_register_command(hass, websocket_get_device)

    websocket_api.async_register_command(hass, websocket_get_aldb)
    websocket_api.async_register_command(hass, websocket_change_aldb_record)
    websocket_api.async_register_command(hass, websocket_create_aldb_record)
    websocket_api.async_register_command(hass, websocket_write_aldb)
    websocket_api.async_register_command(hass, websocket_load_aldb)
    websocket_api.async_register_command(hass, websocket_reset_aldb)
    websocket_api.async_register_command(hass, websocket_add_default_links)
    websocket_api.async_register_command(hass, websocket_notify_on_aldb_status)

    websocket_api.async_register_command(hass, websocket_get_properties)
    websocket_api.async_register_command(hass, websocket_change_properties_record)
    websocket_api.async_register_command(hass, websocket_write_properties)
    websocket_api.async_register_command(hass, websocket_load_properties)
    websocket_api.async_register_command(hass, websocket_reset_properties)
