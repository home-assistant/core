"""Turn Insteon logging on and off."""

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant

from ..const import ID, TYPE


@websocket_api.websocket_command({vol.Required(TYPE): "insteon/logging/get"})
@websocket_api.require_admin
@websocket_api.async_response
async def websocket_get_logging(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Get Insteon log levels."""
    messages = logging.getLogger("pyinsteon.messages")
    topics = logging.getLogger("pyinsteon.topics")

    msg_logging = messages.level == logging.DEBUG
    tpc_logging = topics.level == logging.DEBUG

    connection.send_result(msg[ID], {"messages": msg_logging, "topics": tpc_logging})


@websocket_api.websocket_command(
    {vol.Required(TYPE): "insteon/logging/set", vol.Required("loggers"): list}
)
@websocket_api.require_admin
@websocket_api.async_response
async def websocket_set_logging(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Set Insteon log levels."""
    loggers = msg["loggers"]
    messages = logging.getLogger("pyinsteon.messages")
    topics = logging.getLogger("pyinsteon.topics")

    messages.level = logging.DEBUG if "messages" in loggers else logging.WARNING
    topics.level = logging.DEBUG if "topics" in loggers else logging.WARNING
