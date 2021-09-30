"""Example auth provider."""
from __future__ import annotations

from collections import OrderedDict
from collections.abc import Mapping
import hmac
from typing import Any, cast

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from . import AUTH_PROVIDER_SCHEMA, AUTH_PROVIDERS, AuthProvider, LoginFlow
from ..models import Credentials, UserMeta

# mypy: disallow-any-generics

USER_SCHEMA = vol.Schema(
    {
        vol.Required("username"): str,
        vol.Required("password"): str,
        vol.Optional("name"): str,
    }
)


CONFIG_SCHEMA = AUTH_PROVIDER_SCHEMA.extend(
    {vol.Required("users"): [USER_SCHEMA]}, extra=vol.PREVENT_EXTRA
)


class InvalidAuthError(HomeAssistantError):
    """Raised when submitting invalid authentication."""


@AUTH_PROVIDERS.register("insecure_example")
class ExampleAuthProvider(AuthProvider):
    """Example auth provider based on hardcoded usernames and passwords."""

    async def async_login_flow(self, context: dict[str, Any] | None) -> LoginFlow:
        """Return a flow to login."""
        return ExampleLoginFlow(self)

    @callback
    def async_validate_login(self, username: str, password: str) -> None:
        """Validate a username and password."""
        user = None

        # Compare all users to avoid timing attacks.
        for usr in self.config["users"]:
            if hmac.compare_digest(
                username.encode("utf-8"), usr["username"].encode("utf-8")
            ):
                user = usr

        if user is None:
            # Do one more compare to make timing the same as if user was found.
            hmac.compare_digest(password.encode("utf-8"), password.encode("utf-8"))
            raise InvalidAuthError

        if not hmac.compare_digest(
            user["password"].encode("utf-8"), password.encode("utf-8")
        ):
            raise InvalidAuthError

    async def async_get_or_create_credentials(
        self, flow_result: Mapping[str, str]
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

        Will be used to populate info when creating a new user.
        """
        username = credentials.data["username"]
        name = None

        for user in self.config["users"]:
            if user["username"] == username:
                name = user.get("name")
                break

        return UserMeta(name=name, is_active=True)


class ExampleLoginFlow(LoginFlow):
    """Handler for the login flow."""

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle the step of the form."""
        errors = {}

        if user_input is not None:
            try:
                cast(ExampleAuthProvider, self._auth_provider).async_validate_login(
                    user_input["username"], user_input["password"]
                )
            except InvalidAuthError:
                errors["base"] = "invalid_auth"

            if not errors:
                user_input.pop("password")
                return await self.async_finish(user_input)

        schema: dict[str, type] = OrderedDict()
        schema["username"] = str
        schema["password"] = str

        return self.async_show_form(
            step_id="init", data_schema=vol.Schema(schema), errors=errors
        )
