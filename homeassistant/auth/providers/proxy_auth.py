"""Proxy header auth provider.

It allows to login through the Proxy-User header.
Only use this provider behind a proxy that overwrites the Proxy-User header!
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.auth.models import User
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from . import AUTH_PROVIDER_SCHEMA, AUTH_PROVIDERS, AuthProvider, LoginFlow
from .. import InvalidAuthError
from ..models import Credentials

CONF_PROXY_AUTH = "proxy_auth"
CONF_MAP_USERS = "map_users"
CONF_ALLOW_BYPASS_LOGIN = "allow_bypass_login"

CONFIG_SCHEMA = AUTH_PROVIDER_SCHEMA.extend(
    {
        vol.Optional(CONF_MAP_USERS, default={}): vol.Schema({str: cv.uuid4_hex}),
        vol.Optional(CONF_ALLOW_BYPASS_LOGIN, default=False): cv.boolean,
    },
    extra=vol.PREVENT_EXTRA,
)


@AUTH_PROVIDERS.register(CONF_PROXY_AUTH)
class ProxyAuthProvider(AuthProvider):
    """Proxy auth provider.

    Allow passwordless access using the Proxy-User header.
    """

    DEFAULT_TITLE = "Proxy Authentication"

    @property
    def support_mfa(self) -> bool:
        """Trusted Networks auth provider does not support MFA."""
        return False

    async def async_login_flow(self, context: dict[str, Any] | None) -> LoginFlow:
        """Return a flow to login."""
        assert context is not None
        user_id: str | None = context["headers"].get("Proxy-User")

        if replacement := self.config["map_users"].get(user_id):
            user_id = replacement

        user = next(
            (
                user
                for user in await self.store.async_get_users()
                if not user.system_generated and user.is_active and user.id == user_id
            ),
            None,
        )
        return ProxyHeaderLoginFlow(self, user, self.config[CONF_ALLOW_BYPASS_LOGIN])

    async def async_get_or_create_credentials(
        self, flow_result: Mapping[str, str]
    ) -> Credentials:
        """Get credentials based on the flow result."""
        user_id = flow_result["user"]

        user = await self.store.async_get_user(user_id)
        if not user:
            raise InvalidAuthError
        if not user.is_active:
            raise InvalidAuthError
        if user.system_generated:
            raise InvalidAuthError

        for cred in await self.async_credentials():
            if cred.data["user_id"] == user_id:
                return cred

        cred = self.async_create_credentials({"user_id": user_id})
        await self.store.async_link_user(user, cred)
        return cred


class ProxyHeaderLoginFlow(LoginFlow):
    """Handler for the login flow."""

    def __init__(
        self,
        auth_provider: ProxyAuthProvider,
        user: User | None,
        allow_bypass_login: bool,
    ) -> None:
        """Initialize the login flow."""
        super().__init__(auth_provider)
        self._user = user
        self._allow_bypass_login = allow_bypass_login

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle the step of the form."""
        if not self._user:
            return self.async_abort(reason="not_allowed")

        if self._allow_bypass_login:
            return await self.async_finish({"user": self._user.id})

        if user_input is not None:
            return await self.async_finish(user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {vol.Required("user"): vol.In({self._user.id: self._user.name})}
            ),
        )
