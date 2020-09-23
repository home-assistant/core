"""Websocket API to configure Dynalite from front end."""

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import callback

from .bridge_schema import BRIDGE_SCHEMA


@callback
def async_register_api(hass):
    """Register all of our api endpoints."""
    websocket_api.async_register_command(hass, websocket_get_config_entry_data)
    websocket_api.async_register_command(hass, websocket_update_config_entry_data)


@websocket_api.websocket_command(
    {vol.Required("type"): "dynalite/get_entry", vol.Required("entry_id"): str}
)
def websocket_get_config_entry_data(hass, connection, msg):
    """Get the data of a config entry."""
    connection.send_result(
        msg["id"],
        {"data": dict(hass.config_entries.async_get_entry(msg["entry_id"]).data)},
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "dynalite/update_entry",
        vol.Required("entry_id"): str,
        vol.Required("entry_data"): BRIDGE_SCHEMA,
    }
)
def websocket_update_config_entry_data(hass, connection, msg):
    """Update the data for a config entry."""
    entry_data = msg["entry_data"]
    entry = hass.config_entries.async_get_entry(msg["entry_id"])
    existing_data = entry.data
    if existing_data != entry_data:
        hass.config_entries.async_update_entry(entry, data=entry_data)
    connection.send_result(msg["id"], {})
