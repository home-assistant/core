"""Connection session."""
from __future__ import annotations

import asyncio
from collections.abc import Callable, Hashable
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any

from aiohttp import web
import voluptuous as vol

from homeassistant.auth.models import RefreshToken, User
from homeassistant.components.http import current_request
from homeassistant.core import Context, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, Unauthorized

from . import const, messages
from .util import describe_request

if TYPE_CHECKING:
    from .http import WebSocketAdapter


current_connection = ContextVar["ActiveConnection | None"](
    "current_connection", default=None
)

MessageHandler = Callable[[HomeAssistant, "ActiveConnection", dict[str, Any]], None]
BinaryHandler = Callable[[HomeAssistant, "ActiveConnection", bytes], None]


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
        self.handlers: dict[str, tuple[MessageHandler, vol.Schema]] = self.hass.data[
            const.DOMAIN
        ]
        self.binary_handlers: list[BinaryHandler | None] = []
        current_connection.set(self)

    def get_description(self, request: web.Request | None) -> str:
        """Return a description of the connection."""
        description = self.user.name or ""
        if request:
            description += " " + describe_request(request)
        return description

    def context(self, msg: dict[str, Any]) -> Context:
        """Return a context."""
        return Context(user_id=self.user.id)

    @callback
    def async_register_binary_handler(
        self, handler: BinaryHandler
    ) -> tuple[int, Callable[[], None]]:
        """Register a temporary binary handler for this connection.

        Returns a binary handler_id (1 byte) and a callback to unregister the handler.
        """
        if len(self.binary_handlers) < 255:
            index = len(self.binary_handlers)
            self.binary_handlers.append(None)
        else:
            # Once the list is full, we search for a None entry to reuse.
            index = None
            for idx, existing in enumerate(self.binary_handlers):
                if existing is None:
                    index = idx
                    break

        if index is None:
            raise RuntimeError("Too many binary handlers registered")

        self.binary_handlers[index] = handler

        @callback
        def unsub() -> None:
            """Unregister the handler."""
            assert index is not None
            self.binary_handlers[index] = None

        return index + 1, unsub

    @callback
    def send_result(self, msg_id: int, result: Any | None = None) -> None:
        """Send a result message."""
        self.send_message(messages.result_message(msg_id, result))

    @callback
    def send_event(self, msg_id: int, event: Any | None = None) -> None:
        """Send a event message."""
        self.send_message(messages.event_message(msg_id, event))

    @callback
    def send_error(self, msg_id: int, code: str, message: str) -> None:
        """Send a error message."""
        self.send_message(messages.error_message(msg_id, code, message))

    @callback
    def async_handle_binary(self, handler_id: int, payload: bytes) -> None:
        """Handle a single incoming binary message."""
        index = handler_id - 1
        if (
            index < 0
            or index >= len(self.binary_handlers)
            or (handler := self.binary_handlers[index]) is None
        ):
            self.logger.error(
                "Received binary message for non-existing handler %s", handler_id
            )
            return

        try:
            handler(self.hass, self, payload)
        except Exception:  # pylint: disable=broad-except
            self.logger.exception("Error handling binary message")
            self.binary_handlers[index] = None

    @callback
    def async_handle(self, msg: dict[str, Any]) -> None:
        """Handle a single incoming message."""
        if (
            # Not using isinstance as we don't care about children
            # as these are always coming from JSON
            type(msg) is not dict  # pylint: disable=unidiomatic-typecheck
            or (
                not (cur_id := msg.get("id"))
                or type(cur_id) is not int  # pylint: disable=unidiomatic-typecheck
                or not (type_ := msg.get("type"))
                or type(type_) is not str  # pylint: disable=unidiomatic-typecheck
            )
        ):
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

        if not (handler_schema := self.handlers.get(type_)):
            self.logger.info(f"Received unknown command: {type_}")
            self.send_message(
                messages.error_message(
                    cur_id, const.ERR_UNKNOWN_COMMAND, "Unknown command."
                )
            )
            return

        handler, schema = handler_schema

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

        self.send_message(messages.error_message(msg["id"], code, err_message))

        if code:
            err_message += f" ({code})"
        err_message += " " + self.get_description(current_request.get())

        log_handler("Error handling message: %s", err_message)
