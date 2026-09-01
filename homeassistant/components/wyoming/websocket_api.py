"""Wyoming Websocket API."""

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN
from .models import WyomingConfigEntry

_LOGGER = logging.getLogger(__name__)


@callback
def async_register_websocket_api(hass: HomeAssistant) -> None:
    """Register the websocket API."""
    websocket_api.async_register_command(hass, websocket_info)


@callback
@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): "wyoming/info"})
def websocket_info(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """List service information for Wyoming all config entries."""
    entries: list[WyomingConfigEntry] = hass.config_entries.async_loaded_entries(DOMAIN)

    connection.send_result(
        msg["id"],
        {
            "info": {
                entry.entry_id: entry.runtime_data.service.info.to_dict()
                for entry in entries
            }
        },
    )
