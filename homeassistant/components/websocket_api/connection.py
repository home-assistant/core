"""Connection session."""
import asyncio
from typing import Any, Callable, Dict, Hashable, Optional

import voluptuous as vol

from homeassistant.core import Context, callback
from homeassistant.exceptions import HomeAssistantError, Unauthorized

from . import const, messages

# mypy: allow-untyped-calls, allow-untyped-defs


class ActiveConnection:
    """Handle an active websocket client connection."""

    def __init__(self, logger, hass, send_message, user, refresh_token):
        """Initialize an active connection."""
        self.logger = logger
        self.hass = hass
        self.send_message = send_message
        self.user = user
        if refresh_token:
            self.refresh_token_id = refresh_token.id
        else:
            self.refresh_token_id = None

        self.subscriptions: Dict[Hashable, Callable[[], Any]] = {}
        self.last_id = 0

    def context(self, msg):
        """Return a context."""
        user = self.user
        if user is None:
            return Context()
        return Context(user_id=user.id)

    @callback
    def send_result(self, msg_id: int, result: Optional[Any] = None) -> None:
        """Send a result message."""
        self.send_message(messages.result_message(msg_id, result))

    async def send_big_result(self, msg_id, result):
        """Send a result message that would be expensive to JSON serialize."""
        content = await self.hass.async_add_executor_job(
            const.JSON_DUMP, messages.result_message(msg_id, result)
        )
        self.send_message(content)

    @callback
    def send_error(self, msg_id: int, code: str, message: str) -> None:
        """Send a error message."""
        self.send_message(messages.error_message(msg_id, code, message))

    @callback
    def async_handle(self, msg):
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
            self.logger.error("Received invalid command: {}".format(msg["type"]))
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
    def async_close(self):
        """Close down connection."""
        for unsub in self.subscriptions.values():
            unsub()

    @callback
    def async_handle_exception(self, msg, err):
        """Handle an exception while processing a handler."""
        log_handler = self.logger.error

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
            code = const.ERR_UNKNOWN_ERROR
            err_message = str(err)
        else:
            code = const.ERR_UNKNOWN_ERROR
            err_message = "Unknown error"
            log_handler = self.logger.exception

        log_handler("Error handling message: %s", err_message)

        self.send_message(messages.error_message(msg["id"], code, err_message))
