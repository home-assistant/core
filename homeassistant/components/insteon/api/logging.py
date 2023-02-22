"""Turn Insteon logging on and off."""

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant

from ..const import ID, TYPE

MSG_LOGGER = logging.getLogger("pyinsteon.messages")
TOPIC_LOGGER = logging.getLogger("pyinsteon.topics")


@websocket_api.websocket_command({vol.Required(TYPE): "insteon/logging/get"})
@websocket_api.require_admin
@websocket_api.async_response
async def websocket_get_logging(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Get Insteon log levels."""

    msg_logging = MSG_LOGGER.level == logging.DEBUG
    tpc_logging = TOPIC_LOGGER.level == logging.DEBUG

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

    MSG_LOGGER.setLevel(logging.DEBUG if "messages" in loggers else logging.WARNING)
    TOPIC_LOGGER.setLevel(logging.DEBUG if "topics" in loggers else logging.WARNING)
