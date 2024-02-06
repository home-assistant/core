"""Handle the auth of a connection."""
from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING, Any, Final

from aiohttp.web import Request
import voluptuous as vol
from voluptuous.humanize import humanize_error

from homeassistant.components.http.ban import process_success_login, process_wrong_login
from homeassistant.const import __version__
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers.json import json_bytes
from homeassistant.util.json import JsonValueType

from .connection import ActiveConnection
from .error import Disconnect

if TYPE_CHECKING:
    from .http import WebSocketAdapter


TYPE_AUTH: Final = "auth"
TYPE_AUTH_INVALID: Final = "auth_invalid"
TYPE_AUTH_OK: Final = "auth_ok"
TYPE_AUTH_REQUIRED: Final = "auth_required"

AUTH_MESSAGE_SCHEMA: Final = vol.Schema(
    {
        vol.Required("type"): TYPE_AUTH,
        vol.Exclusive("api_password", "auth"): str,
        vol.Exclusive("access_token", "auth"): str,
    }
)

AUTH_OK_MESSAGE = json_bytes({"type": TYPE_AUTH_OK, "ha_version": __version__})
AUTH_REQUIRED_MESSAGE = json_bytes(
    {"type": TYPE_AUTH_REQUIRED, "ha_version": __version__}
)


def auth_invalid_message(message: str) -> bytes:
    """Return an auth_invalid message."""
    return json_bytes({"type": TYPE_AUTH_INVALID, "message": message})


class AuthPhase:
    """Connection that requires client to authenticate first."""

    def __init__(
        self,
        logger: WebSocketAdapter,
        hass: HomeAssistant,
        send_message: Callable[[bytes | str | dict[str, Any]], None],
        cancel_ws: CALLBACK_TYPE,
        request: Request,
        send_bytes_text: Callable[[bytes], Coroutine[Any, Any, None]],
    ) -> None:
        """Initialize the authenticated connection."""
        self._hass = hass
        # send_message will send a message to the client via the queue.
        self._send_message = send_message
        self._cancel_ws = cancel_ws
        self._logger = logger
        self._request = request
        # send_bytes_text will directly send a message to the client.
        self._send_bytes_text = send_bytes_text

    async def async_handle(self, msg: JsonValueType) -> ActiveConnection:
        """Handle authentication."""
        try:
            valid_msg = AUTH_MESSAGE_SCHEMA(msg)
        except vol.Invalid as err:
            error_msg = (
                f"Auth message incorrectly formatted: {humanize_error(msg, err)}"
            )
            self._logger.warning(error_msg)
            await self._send_bytes_text(auth_invalid_message(error_msg))
            raise Disconnect from err

        if (access_token := valid_msg.get("access_token")) and (
            refresh_token := self._hass.auth.async_validate_access_token(access_token)
        ):
            conn = ActiveConnection(
                self._logger,
                self._hass,
                self._send_message,
                refresh_token.user,
                refresh_token,
            )
            conn.subscriptions[
                "auth"
            ] = self._hass.auth.async_register_revoke_token_callback(
                refresh_token.id, self._cancel_ws
            )
            await self._send_bytes_text(AUTH_OK_MESSAGE)
            self._logger.debug("Auth OK")
            process_success_login(self._request)
            return conn

        await self._send_bytes_text(
            auth_invalid_message("Invalid access token or password")
        )
        await process_wrong_login(self._request)
        raise Disconnect
