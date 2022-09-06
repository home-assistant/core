"""Connection session."""
from __future__ import annotations

import asyncio
from collections.abc import Callable, Hashable
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.auth.models import RefreshToken, User
from homeassistant.core import Context, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, Unauthorized

from . import const, messages

if TYPE_CHECKING:
    from .http import WebSocketAdapter


current_connection = ContextVar["ActiveConnection | None"](
    "current_connection", default=None
)


class ActiveConnection:
    """Handle an active websocket client connection."""

    def __init__(
        self,
        logger: WebSocketAdapter,
        hass: HomeAssistant,
        send_message: Callable[[str | dict[str, Any] | Callable[[], str]], None],
        user: User,
        refresh_token: RefreshToken,
    ) -> None:
        """Initialize an active connection."""
        self.logger = logger
        self.hass = hass
        self.send_message = send_message
        self.user = user
        self.refresh_token_id = refresh_token.id
        self.subscriptions: dict[Hashable, Callable[[], Any]] = {}
        self.last_id = 0
        self.supported_features: dict[str, float] = {}
        current_connection.set(self)

    def context(self, msg: dict[str, Any]) -> Context:
        """Return a context."""
        return Context(user_id=self.user.id)

    @callback
    def send_result(self, msg_id: int, result: Any | None = None) -> None:
        """Send a result message."""
        self.send_message(messages.result_message(msg_id, result))

    @callback
    def send_error(self, msg_id: int, code: str, message: str) -> None:
        """Send a error message."""
        self.send_message(messages.error_message(msg_id, code, message))

    @callback
    def async_handle(self, msg: dict[str, Any]) -> None:
        """Handle a single incoming message."""
        handlers = self.hass.data[const.DOMAIN]

        try:
            msg = messages.MINIMAL_MESSAGE_SCHEMA(msg)
            cur_id = msg["id"]
        except vol.Invalid:
            self.logger.error("Received invalid command", msg)
            self.send_message(
                messages.error_message(
                    msg.get("id"),
                    const.ERR_INVALID_FORMAT,
                    "Message incorrectly formatted.",
                )
            )
            return

        if cur_id <= self.last_id:
            self.send_message(
                messages.error_message(
                    cur_id, const.ERR_ID_REUSE, "Identifier values have to increase."
                )
            )
            return

        if msg["type"] not in handlers:
            self.logger.info("Received unknown command: {}".format(msg["type"]))
            self.send_message(
                messages.error_message(
                    cur_id, const.ERR_UNKNOWN_COMMAND, "Unknown command."
                )
            )
            return

        handler, schema = handlers[msg["type"]]

        try:
            handler(self.hass, self, schema(msg))
        except Exception as err:  # pylint: disable=broad-except
            self.async_handle_exception(msg, err)

        self.last_id = cur_id

    @callback
    def async_handle_close(self) -> None:
        """Handle closing down connection."""
        for unsub in self.subscriptions.values():
            unsub()

    @callback
    def async_handle_exception(self, msg: dict[str, Any], err: Exception) -> None:
        """Handle an exception while processing a handler."""
        log_handler = self.logger.error

        code = const.ERR_UNKNOWN_ERROR
        err_message = None

        if isinstance(err, Unauthorized):
            code = const.ERR_UNAUTHORIZED
            err_message = "Unauthorized"
        elif isinstance(err, vol.Invalid):
            code = const.ERR_INVALID_FORMAT
            err_message = vol.humanize.humanize_error(msg, err)
        elif isinstance(err, asyncio.TimeoutError):
            code = const.ERR_TIMEOUT
            err_message = "Timeout"
        elif isinstance(err, HomeAssistantError):
            err_message = str(err)

        # This if-check matches all other errors but also matches errors which
        # result in an empty message. In that case we will also log the stack
        # trace so it can be fixed.
        if not err_message:
            err_message = "Unknown error"
            log_handler = self.logger.exception

        log_handler("Error handling message: %s (%s)", err_message, code)

        self.send_message(messages.error_message(msg["id"], code, err_message))
