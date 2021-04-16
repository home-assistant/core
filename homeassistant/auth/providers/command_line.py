"""Auth provider that validates credentials via an external command."""
from __future__ import annotations

import asyncio.subprocess
import collections
import logging
import os
from typing import Any, cast

import voluptuous as vol

from homeassistant.const import CONF_COMMAND
from homeassistant.exceptions import HomeAssistantError

from . import AUTH_PROVIDER_SCHEMA, AUTH_PROVIDERS, AuthProvider, LoginFlow
from ..models import Credentials, UserMeta

CONF_ARGS = "args"
CONF_META = "meta"

CONFIG_SCHEMA = AUTH_PROVIDER_SCHEMA.extend(
    {
        vol.Required(CONF_COMMAND): vol.All(
            str, os.path.normpath, msg="must be an absolute path"
        ),
        vol.Optional(CONF_ARGS, default=None): vol.Any(vol.DefaultTo(list), [str]),
        vol.Optional(CONF_META, default=False): bool,
    },
    extra=vol.PREVENT_EXTRA,
)

_LOGGER = logging.getLogger(__name__)


class InvalidAuthError(HomeAssistantError):
    """Raised when authentication with given credentials fails."""


@AUTH_PROVIDERS.register("command_line")
class CommandLineAuthProvider(AuthProvider):
    """Auth provider validating credentials by calling a command."""

    DEFAULT_TITLE = "Command Line Authentication"

    # which keys to accept from a program's stdout
    ALLOWED_META_KEYS = ("name",)

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Extend parent's __init__.

        Adds self._user_meta dictionary to hold the user-specific
        attributes provided by external programs.
        """
        super().__init__(*args, **kwargs)
        self._user_meta: dict[str, dict[str, Any]] = {}

    async def async_login_flow(self, context: dict | None) -> LoginFlow:
        """Return a flow to login."""
        return CommandLineLoginFlow(self)

    async def async_validate_login(self, username: str, password: str) -> None:
        """Validate a username and password."""
        env = {"username": username, "password": password}
        try:
            process = await asyncio.subprocess.create_subprocess_exec(  # pylint: disable=no-member
                self.config[CONF_COMMAND],
                *self.config[CONF_ARGS],
                env=env,
                stdout=asyncio.subprocess.PIPE if self.config[CONF_META] else None,
            )
            stdout, _ = await process.communicate()
        except OSError as err:
            # happens when command doesn't exist or permission is denied
            _LOGGER.error("Error while authenticating %r: %s", username, err)
            raise InvalidAuthError from err

        if process.returncode != 0:
            _LOGGER.error(
                "User %r failed to authenticate, command exited with code %d",
                username,
                process.returncode,
            )
            raise InvalidAuthError

        if self.config[CONF_META]:
            meta: dict[str, str] = {}
            for _line in stdout.splitlines():
                try:
                    line = _line.decode().lstrip()
                    if line.startswith("#"):
                        continue
                    key, value = line.split("=", 1)
                except ValueError:
                    # malformed line
                    continue
                key = key.strip()
                value = value.strip()
                if key in self.ALLOWED_META_KEYS:
                    meta[key] = value
            self._user_meta[username] = meta

    async def async_get_or_create_credentials(
        self, flow_result: dict[str, str]
    ) -> Credentials:
        """Get credentials based on the flow result."""
        username = flow_result["username"]
        for credential in await self.async_credentials():
            if credential.data["username"] == username:
                return credential

        # Create new credentials.
        return self.async_create_credentials({"username": username})

    async def async_user_meta_for_credentials(
        self, credentials: Credentials
    ) -> UserMeta:
        """Return extra user metadata for credentials.

        Currently, only name is supported.
        """
        meta = self._user_meta.get(credentials.data["username"], {})
        return UserMeta(name=meta.get("name"), is_active=True)


class CommandLineLoginFlow(LoginFlow):
    """Handler for the login flow."""

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> dict[str, Any]:
        """Handle the step of the form."""
        errors = {}

        if user_input is not None:
            user_input["username"] = user_input["username"].strip()
            try:
                await cast(
                    CommandLineAuthProvider, self._auth_provider
                ).async_validate_login(user_input["username"], user_input["password"])
            except InvalidAuthError:
                errors["base"] = "invalid_auth"

            if not errors:
                user_input.pop("password")
                return await self.async_finish(user_input)

        schema: dict[str, type] = collections.OrderedDict()
        schema["username"] = str
        schema["password"] = str

        return self.async_show_form(
            step_id="init", data_schema=vol.Schema(schema), errors=errors
        )
