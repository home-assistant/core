"""Shared decorators and utilities for Matter WebSocket API."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from functools import wraps
from typing import Any, Concatenate

from matter_server.client.models.node import MatterNode
from matter_server.common.errors import MatterError

from homeassistant.components.websocket_api import ActiveConnection
from homeassistant.core import HomeAssistant

from .adapter import MatterAdapter
from .helpers import MissingNode, get_matter, node_from_ha_device_id

ID = "id"
TYPE = "type"
DEVICE_ID = "device_id"

ERROR_NODE_NOT_FOUND = "node_not_found"


def async_get_node(
    func: Callable[
        [HomeAssistant, ActiveConnection, dict[str, Any], MatterAdapter, MatterNode],
        Coroutine[Any, Any, None],
    ],
) -> Callable[
    [HomeAssistant, ActiveConnection, dict[str, Any], MatterAdapter],
    Coroutine[Any, Any, None],
]:
    """Decorate async function to get node."""

    @wraps(func)
    async def async_get_node_func(
        hass: HomeAssistant,
        connection: ActiveConnection,
        msg: dict[str, Any],
        matter: MatterAdapter,
    ) -> None:
        """Provide user specific data and store to function."""
        node = node_from_ha_device_id(hass, msg[DEVICE_ID])
        if not node:
            raise MissingNode(
                f"Could not resolve Matter node from device id {msg[DEVICE_ID]}"
            )
        await func(hass, connection, msg, matter, node)

    return async_get_node_func


def async_get_matter_adapter(
    func: Callable[
        [HomeAssistant, ActiveConnection, dict[str, Any], MatterAdapter],
        Coroutine[Any, Any, None],
    ],
) -> Callable[
    [HomeAssistant, ActiveConnection, dict[str, Any]], Coroutine[Any, Any, None]
]:
    """Decorate function to get the MatterAdapter."""

    @wraps(func)
    async def _get_matter(
        hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
    ) -> None:
        """Provide the Matter client to the function."""
        matter = get_matter(hass)

        await func(hass, connection, msg, matter)

    return _get_matter


def async_handle_failed_command[**_P](
    func: Callable[
        Concatenate[HomeAssistant, ActiveConnection, dict[str, Any], _P],
        Coroutine[Any, Any, None],
    ],
) -> Callable[
    Concatenate[HomeAssistant, ActiveConnection, dict[str, Any], _P],
    Coroutine[Any, Any, None],
]:
    """Decorate function to handle MatterError and send relevant error."""

    @wraps(func)
    async def async_handle_failed_command_func(
        hass: HomeAssistant,
        connection: ActiveConnection,
        msg: dict[str, Any],
        *args: _P.args,
        **kwargs: _P.kwargs,
    ) -> None:
        """Handle MatterError within function and send relevant error."""
        try:
            await func(hass, connection, msg, *args, **kwargs)
        except MatterError as err:
            connection.send_error(msg[ID], str(err.error_code), err.args[0])
        except MissingNode as err:
            connection.send_error(msg[ID], ERROR_NODE_NOT_FOUND, err.args[0])

    return async_handle_failed_command_func
