"""ESPHome websocket API."""

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .const import CONF_NOISE_PSK

_LOGGER = logging.getLogger(__name__)


TYPE = "type"
ENTRY_ID = "entry_id"


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Set up the websocket API."""
    websocket_api.async_register_command(hass, get_encryption_key)


@callback
@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "esphome/get_encryption_key",
        vol.Required(ENTRY_ID): str,
    }
)
def get_encryption_key(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Get the encryption key for an ESPHome config entry."""
    entry = hass.config_entries.async_get_entry(msg[ENTRY_ID])
    if entry is None:
        connection.send_error(
            msg["id"], websocket_api.ERR_NOT_FOUND, "Config entry not found"
        )
        return

    connection.send_result(
        msg["id"],
        {
            "encryption_key": entry.data.get(CONF_NOISE_PSK),
        },
    )
