"""Authentication and login handling for the Matrix component."""

from __future__ import annotations

import logging

from nio import AsyncClient
from nio.responses import LoginError, WhoamiError, WhoamiResponse

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.json import save_json
from homeassistant.util.json import JsonObjectType, load_json_object

_LOGGER = logging.getLogger(__name__)


class MatrixAuth:
    """Handle Matrix authentication and session management."""

    def __init__(self, hass: HomeAssistant, session_filepath: str) -> None:
        """Initialize authentication handler."""
        self.hass = hass
        self._session_filepath = session_filepath
        self._access_tokens: JsonObjectType = {}

    async def get_auth_tokens(self) -> JsonObjectType:
        """Read authentication tokens from disk."""
        try:
            self._access_tokens = await self.hass.async_add_executor_job(
                load_json_object, self._session_filepath
            )
        except HomeAssistantError as ex:
            _LOGGER.warning(
                "Loading authentication tokens from file '%s' failed: %s",
                self._session_filepath,
                str(ex),
            )
            self._access_tokens = {}
        return self._access_tokens

    async def store_auth_token(self, client: AsyncClient, token: str) -> None:
        """Store authentication token to session and persistent storage."""
        self._access_tokens[client.user_id] = token

        await self.hass.async_add_executor_job(
            save_json,
            self._session_filepath,
            self._access_tokens,
            True,  # private=True
        )

    async def login(self, client: AsyncClient, mx_id: str, password: str) -> None:
        """Log in to the Matrix homeserver.

        Attempts to use the stored access token.
        If that fails, then tries using the password.
        If that also fails, raises ConfigEntryAuthFailed.
        """
        # If we have an access token
        if (token := self._access_tokens.get(mx_id)) is not None:
            _LOGGER.debug("Restoring login from stored access token")
            client.access_token = token
            response = await client.whoami()
            if isinstance(response, WhoamiError):
                _LOGGER.warning(
                    "Restoring login from access token failed: %s, %s",
                    response.status_code,
                    response.message,
                )
                client.access_token = (
                    ""  # Force a soft-logout if the homeserver didn't.
                )
            elif isinstance(response, WhoamiResponse):
                _LOGGER.debug(
                    "Successfully restored login from access token: user_id '%s', device_id '%s'",
                    response.user_id,
                    response.device_id,
                )
                # Only call restore_login if whoami succeeded
                await self.hass.async_add_executor_job(
                    client.restore_login,
                    mx_id,
                    client.device_id,
                    token,
                )

        # If the token login did not succeed
        if not client.logged_in:
            response = await client.login(password=password)
            _LOGGER.debug("Logging in using password")

            if isinstance(response, LoginError):
                _LOGGER.error(
                    "Login by password failed: %s, %s",
                    response.status_code,
                    response.message,
                )
            if client.logged_in:
                await self.store_auth_token(client, client.access_token)

        if not client.logged_in:
            raise ConfigEntryAuthFailed(
                "Login failed, both token and username/password are invalid"
            )
