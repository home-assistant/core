"""Handle the auth of a connection."""
from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Final

from aiohttp.web import Request
import voluptuous as vol
from voluptuous.humanize import humanize_error

from homeassistant.auth.models import RefreshToken, User
from homeassistant.components.http.ban import process_success_login, process_wrong_login
from homeassistant.const import __version__
from homeassistant.core import HomeAssistant

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


def auth_ok_message() -> dict[str, str]:
    """Return an auth_ok message."""
    return {"type": TYPE_AUTH_OK, "ha_version": __version__}


def auth_required_message() -> dict[str, str]:
    """Return an auth_required message."""
    return {"type": TYPE_AUTH_REQUIRED, "ha_version": __version__}


def auth_invalid_message(message: str) -> dict[str, str]:
    """Return an auth_invalid message."""
    return {"type": TYPE_AUTH_INVALID, "message": message}


class AuthPhase:
    """Connection that requires client to authenticate first."""

    def __init__(
        self,
        logger: WebSocketAdapter,
        hass: HomeAssistant,
        send_message: Callable[[str | dict[str, Any]], None],
        request: Request,
    ) -> None:
        """Initialize the authentiated connection."""
        self._hass = hass
        self._send_message = send_message
        self._logger = logger
        self._request = request

    async def async_handle(self, msg: dict[str, str]) -> ActiveConnection:
        """Handle authentication."""
        try:
            msg = AUTH_MESSAGE_SCHEMA(msg)
        except vol.Invalid as err:
            error_msg = (
                f"Auth message incorrectly formatted: {humanize_error(msg, err)}"
            )
            self._logger.warning(error_msg)
            self._send_message(auth_invalid_message(error_msg))
            raise Disconnect from err

        if "access_token" in msg:
            self._logger.debug("Received access_token")
            refresh_token = await self._hass.auth.async_validate_access_token(
                msg["access_token"]
            )
            if refresh_token is not None:
                return await self._async_finish_auth(refresh_token.user, refresh_token)

        self._send_message(auth_invalid_message("Invalid access token or password"))
        await process_wrong_login(self._request)
        raise Disconnect

    async def _async_finish_auth(
        self, user: User, refresh_token: RefreshToken
    ) -> ActiveConnection:
        """Create an active connection."""
        self._logger.debug("Auth OK")
        await process_success_login(self._request)
        self._send_message(auth_ok_message())
        return ActiveConnection(
            self._logger, self._hass, self._send_message, user, refresh_token
        )
