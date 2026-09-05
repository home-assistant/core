"""Websocket API for the Infrared integration."""

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .code import signal_to_code
from .entity import InfraredReceivedSignal
from .helpers import async_subscribe_receiver

_LOGGER = logging.getLogger(__name__)


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Register the infrared websocket commands."""
    websocket_api.async_register_command(hass, websocket_subscribe_receiver)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "infrared/receiver/subscribe",
        vol.Required("entity_id"): cv.entity_id,
    }
)
@callback
def websocket_subscribe_receiver(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Forward the codes a receiver picks up to the websocket.

    Used by the automation editor to capture the codes of a remote.
    """

    @callback
    def forward_signal(signal: InfraredReceivedSignal) -> None:
        """Forward a received signal as a pronto hex code."""
        try:
            code = signal_to_code(signal)
        except ValueError:
            _LOGGER.debug("Discarding unusable signal: %s", signal)
            return
        connection.send_event(msg["id"], {"code": code})

    try:
        connection.subscriptions[msg["id"]] = async_subscribe_receiver(
            hass, msg["entity_id"], forward_signal
        )
    except HomeAssistantError as err:
        connection.send_error(msg["id"], websocket_api.ERR_NOT_FOUND, str(err))
        return

    connection.send_result(msg["id"])
