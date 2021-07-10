"""Decorators for the Websocket API."""
from __future__ import annotations

import asyncio
from functools import wraps
from typing import Any, Callable

import voluptuous as vol

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import Unauthorized

from . import const, messages
from .connection import ActiveConnection


async def _handle_async_response(
    func: const.AsyncWebSocketCommandHandler,
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Create a response and handle exception."""
    try:
        await func(hass, connection, msg)
    except Exception as err:  # pylint: disable=broad-except
        connection.async_handle_exception(msg, err)


def async_response(
    func: const.AsyncWebSocketCommandHandler,
) -> const.WebSocketCommandHandler:
    """Decorate an async function to handle WebSocket API messages."""

    @callback
    @wraps(func)
    def schedule_handler(
        hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
    ) -> None:
        """Schedule the handler."""
        # As the webserver is now started before the start
        # event we do not want to block for websocket responders
        asyncio.create_task(_handle_async_response(func, hass, connection, msg))

    return schedule_handler


def require_admin(func: const.WebSocketCommandHandler) -> const.WebSocketCommandHandler:
    """Websocket decorator to require user to be an admin."""

    @wraps(func)
    def with_admin(
        hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
    ) -> None:
        """Check admin and call function."""
        user = connection.user

        if user is None or not user.is_admin:
            raise Unauthorized()

        func(hass, connection, msg)

    return with_admin


def ws_require_user(
    only_owner: bool = False,
    only_system_user: bool = False,
    allow_system_user: bool = True,
    only_active_user: bool = True,
    only_inactive_user: bool = False,
) -> Callable[[const.WebSocketCommandHandler], const.WebSocketCommandHandler]:
    """Decorate function validating login user exist in current WS connection.

    Will write out error message if not authenticated.
    """

    def validator(func: const.WebSocketCommandHandler) -> const.WebSocketCommandHandler:
        """Decorate func."""

        @wraps(func)
        def check_current_user(
            hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
        ) -> None:
            """Check current user."""

            def output_error(message_id: str, message: str) -> None:
                """Output error message."""
                connection.send_message(
                    messages.error_message(msg["id"], message_id, message)
                )

            if only_owner and not connection.user.is_owner:
                output_error("only_owner", "Only allowed as owner")
                return

            if only_system_user and not connection.user.system_generated:
                output_error("only_system_user", "Only allowed as system user")
                return

            if not allow_system_user and connection.user.system_generated:
                output_error("not_system_user", "Not allowed as system user")
                return

            if only_active_user and not connection.user.is_active:
                output_error("only_active_user", "Only allowed as active user")
                return

            if only_inactive_user and connection.user.is_active:
                output_error("only_inactive_user", "Not allowed as active user")
                return

            return func(hass, connection, msg)

        return check_current_user

    return validator


def websocket_command(
    schema: dict[vol.Marker, Any],
) -> Callable[[const.WebSocketCommandHandler], const.WebSocketCommandHandler]:
    """Tag a function as a websocket command."""
    command = schema["type"]

    def decorate(func: const.WebSocketCommandHandler) -> const.WebSocketCommandHandler:
        """Decorate ws command function."""
        # pylint: disable=protected-access
        func._ws_schema = messages.BASE_COMMAND_MESSAGE_SCHEMA.extend(schema)  # type: ignore[attr-defined]
        func._ws_command = command  # type: ignore[attr-defined]
        return func

    return decorate
