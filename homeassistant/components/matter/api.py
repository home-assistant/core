"""Handle websocket api for Matter."""
from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any

from matter_server.client import MatterClient
from matter_server.client.exceptions import FailedCommand
import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.websocket_api import ActiveConnection
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN

ID = "id"
TYPE = "type"


@callback
def async_register_api(hass: HomeAssistant) -> None:
    """Register all of our api endpoints."""
    websocket_api.async_register_command(hass, websocket_commission)


def async_get_matter(func: Callable) -> Callable:
    """Decorate function to get the Matter client."""

    @wraps(func)
    async def _get_matter(
        hass: HomeAssistant, connection: ActiveConnection, msg: dict
    ) -> None:
        """Provide the Matter client to the function."""
        matter: MatterClient = next(iter(hass.data[DOMAIN].values()))

        await func(hass, connection, msg, matter)

    return _get_matter


def async_handle_failed_command(func: Callable) -> Callable:
    """Decorate function to handle FailedCommand and send relevant error."""

    @wraps(func)
    async def async_handle_failed_command_func(
        hass: HomeAssistant,
        connection: ActiveConnection,
        msg: dict[str, Any],
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Handle FailedCommand within function and send relevant error."""
        try:
            await func(hass, connection, msg, *args, **kwargs)
        except FailedCommand as err:
            connection.send_error(msg[ID], err.error_code, err.args[0])

    return async_handle_failed_command_func


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "matter/commission",
        vol.Required("code"): str,
    }
)
@websocket_api.async_response
@async_handle_failed_command
@async_get_matter
async def websocket_commission(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
    matter: MatterClient,
) -> None:
    """Commission a device to the Matter network."""
    await matter.commission_with_code(msg["code"])
    connection.send_result(msg[ID])
