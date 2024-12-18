"""Header auth provider.

It shows list of users if accessed with a configured header.
Abort login flow if not accessed with a configured header.
"""

from __future__ import annotations

from collections.abc import Mapping
import hashlib
import hmac
from ipaddress import IPv4Address, IPv4Network, IPv6Address, IPv6Network
from typing import cast

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.network import is_cloud_connection

from .. import InvalidAuthError
from ..models import (
    AuthFlowContext,
    AuthFlowResult,
    Credentials,
    RefreshFlowContext,
    RefreshToken,
    UserMeta,
)
from . import AUTH_PROVIDER_SCHEMA, AUTH_PROVIDERS, AuthProvider, LoginFlow

type IPAddress = IPv4Address | IPv6Address
type IPNetwork = IPv4Network | IPv6Network

HEADER_NAME = "x-homeassistant-token"
CONF_HEADER = "header"
CONF_TOKEN_SHA256 = "token_sha256"
CONF_ALLOW_BYPASS_LOGIN = "allow_bypass_login"

CONFIG_SCHEMA = AUTH_PROVIDER_SCHEMA.extend(
    {
        vol.Required(CONF_TOKEN_SHA256): cv.string,
        vol.Optional(CONF_ALLOW_BYPASS_LOGIN, default=False): cv.boolean,
    },
    extra=vol.PREVENT_EXTRA,
)


class InvalidUserError(HomeAssistantError):
    """Raised when try to login as invalid user."""


@AUTH_PROVIDERS.register("header")
class HeaderAuthProvider(AuthProvider):
    """Header auth provider.

    Allow passwordless access using header.
    """

    DEFAULT_TITLE = "Header"

    @property
    def token_sha256(self) -> str:
        """Return expected header value."""
        return cast(str, self.config[CONF_TOKEN_SHA256])

    @property
    def support_mfa(self) -> bool:
        """Header auth provider does not support MFA."""
        return False

    async def async_login_flow(self, context: AuthFlowContext | None) -> LoginFlow:
        """Return a flow to login."""
        assert context is not None
        header = context["headers"].get(HEADER_NAME)
        users = await self.store.async_get_users()
        available_users = [
            user for user in users if not user.system_generated and user.is_active
        ]
        return HeaderLoginFlow(
            self,
            header,
            {user.id: user.name for user in available_users},
            self.config[CONF_ALLOW_BYPASS_LOGIN],
        )

    async def async_get_or_create_credentials(
        self, flow_result: Mapping[str, str]
    ) -> Credentials:
        """Get credentials based on the flow result."""
        user_id = flow_result["user"]

        users = await self.store.async_get_users()
        for user in users:
            if user.id != user_id:
                continue

            if user.system_generated:
                continue

            if not user.is_active:
                continue

            for credential in await self.async_credentials():
                if credential.data["user_id"] == user_id:
                    return credential

            cred = self.async_create_credentials({"user_id": user_id})
            await self.store.async_link_user(user, cred)
            return cred

        # We only allow login as exist user
        raise InvalidUserError

    async def async_user_meta_for_credentials(
        self, credentials: Credentials
    ) -> UserMeta:
        """Return extra user metadata for credentials.

        Header auth provider should never create new user.
        """
        raise NotImplementedError

    @callback
    def async_validate_access(self, header: str | None) -> None:
        """Make sure the access is with the correct header.

        Raise InvalidAuthError if not.
        """

        if not header:
            raise InvalidAuthError("Can't allow access without header")

        hashed = hashlib.sha256(header.encode("utf-8")).hexdigest()

        if not hmac.compare_digest(hashed, self.token_sha256):
            raise InvalidAuthError("Can't allow access without header")

        if is_cloud_connection(self.hass):
            raise InvalidAuthError("Can't allow access from Home Assistant Cloud")

    @callback
    def async_validate_refresh_token(
        self,
        refresh_token: RefreshToken,
        context: RefreshFlowContext,
    ) -> None:
        """Verify a refresh token is still valid."""
        if context.get("headers") is None:
            raise InvalidAuthError("Headers needed for headers auth provider.")

        self.async_validate_access(context["headers"].get(HEADER_NAME))


class HeaderLoginFlow(LoginFlow):
    """Handler for the login flow."""

    def __init__(
        self,
        auth_provider: HeaderAuthProvider,
        header: str | None,
        available_users: dict[str, str | None],
        allow_bypass_login: bool,
    ) -> None:
        """Initialize the login flow."""
        super().__init__(auth_provider)
        self._available_users = available_users
        self._header = header
        self._allow_bypass_login = allow_bypass_login

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> AuthFlowResult:
        """Handle the step of the form."""
        try:
            cast(HeaderAuthProvider, self._auth_provider).async_validate_access(
                self._header
            )

        except InvalidAuthError:
            return self.async_abort(reason="not_allowed")

        if user_input is not None:
            return await self.async_finish(user_input)

        if self._allow_bypass_login and len(self._available_users) == 1:
            return await self.async_finish(
                {"user": next(iter(self._available_users.keys()))}
            )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {vol.Required("user"): vol.In(self._available_users)}
            ),
        )
