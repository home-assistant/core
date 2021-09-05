"""Trusted Networks auth provider.

It shows list of users if access from trusted network.
Abort login flow if not access from trusted network.
"""
from __future__ import annotations

from collections.abc import Mapping
from ipaddress import (
    IPv4Address,
    IPv4Network,
    IPv6Address,
    IPv6Network,
    ip_address,
    ip_network,
)
from typing import Any, Dict, List, Union, cast

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv

from . import AUTH_PROVIDER_SCHEMA, AUTH_PROVIDERS, AuthProvider, LoginFlow
from .. import InvalidAuthError
from ..models import Credentials, RefreshToken, UserMeta

# mypy: disallow-any-generics

IPAddress = Union[IPv4Address, IPv6Address]
IPNetwork = Union[IPv4Network, IPv6Network]

CONF_TRUSTED_NETWORKS = "trusted_networks"
CONF_TRUSTED_USERS = "trusted_users"
CONF_GROUP = "group"
CONF_ALLOW_BYPASS_LOGIN = "allow_bypass_login"

CONFIG_SCHEMA = AUTH_PROVIDER_SCHEMA.extend(
    {
        vol.Required(CONF_TRUSTED_NETWORKS): vol.All(cv.ensure_list, [ip_network]),
        vol.Optional(CONF_TRUSTED_USERS, default={}): vol.Schema(
            # we only validate the format of user_id or group_id
            {
                ip_network: vol.All(
                    cv.ensure_list,
                    [
                        vol.Or(
                            cv.uuid4_hex,
                            vol.Schema({vol.Required(CONF_GROUP): cv.uuid4_hex}),
                        )
                    ],
                )
            }
        ),
        vol.Optional(CONF_ALLOW_BYPASS_LOGIN, default=False): cv.boolean,
    },
    extra=vol.PREVENT_EXTRA,
)


class InvalidUserError(HomeAssistantError):
    """Raised when try to login as invalid user."""


@AUTH_PROVIDERS.register("trusted_networks")
class TrustedNetworksAuthProvider(AuthProvider):
    """Trusted Networks auth provider.

    Allow passwordless access from trusted network.
    """

    DEFAULT_TITLE = "Trusted Networks"

    @property
    def trusted_networks(self) -> list[IPNetwork]:
        """Return trusted networks."""
        return cast(List[IPNetwork], self.config[CONF_TRUSTED_NETWORKS])

    @property
    def trusted_users(self) -> dict[IPNetwork, Any]:
        """Return trusted users per network."""
        return cast(Dict[IPNetwork, Any], self.config[CONF_TRUSTED_USERS])

    @property
    def trusted_proxies(self) -> list[IPNetwork]:
        """Return trusted proxies in the system."""
        if not self.hass.http:
            return []

        return [
            ip_network(trusted_proxy)
            for trusted_proxy in self.hass.http.trusted_proxies
        ]

    @property
    def support_mfa(self) -> bool:
        """Trusted Networks auth provider does not support MFA."""
        return False

    async def async_login_flow(self, context: dict[str, Any] | None) -> LoginFlow:
        """Return a flow to login."""
        assert context is not None
        ip_addr = cast(IPAddress, context.get("ip_address"))
        users = await self.store.async_get_users()
        available_users = [
            user for user in users if not user.system_generated and user.is_active
        ]
        for ip_net, user_or_group_list in self.trusted_users.items():
            if ip_addr not in ip_net:
                continue

            user_list = [
                user_id for user_id in user_or_group_list if isinstance(user_id, str)
            ]
            group_list = [
                group[CONF_GROUP]
                for group in user_or_group_list
                if isinstance(group, dict)
            ]
            flattened_group_list = [
                group for sublist in group_list for group in sublist
            ]
            available_users = [
                user
                for user in available_users
                if (
                    user.id in user_list
                    or any(group.id in flattened_group_list for group in user.groups)
                )
            ]
            break

        return TrustedNetworksLoginFlow(
            self,
            ip_addr,
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

        Trusted network auth provider should never create new user.
        """
        raise NotImplementedError

    @callback
    def async_validate_access(self, ip_addr: IPAddress) -> None:
        """Make sure the access from trusted networks.

        Raise InvalidAuthError if not.
        Raise InvalidAuthError if trusted_networks is not configured.
        """
        if not self.trusted_networks:
            raise InvalidAuthError("trusted_networks is not configured")

        if not any(
            ip_addr in trusted_network for trusted_network in self.trusted_networks
        ):
            raise InvalidAuthError("Not in trusted_networks")

        if any(ip_addr in trusted_proxy for trusted_proxy in self.trusted_proxies):
            raise InvalidAuthError("Can't allow access from a proxy server")

    @callback
    def async_validate_refresh_token(
        self, refresh_token: RefreshToken, remote_ip: str | None = None
    ) -> None:
        """Verify a refresh token is still valid."""
        if remote_ip is None:
            raise InvalidAuthError(
                "Unknown remote ip can't be used for trusted network provider."
            )
        self.async_validate_access(ip_address(remote_ip))


class TrustedNetworksLoginFlow(LoginFlow):
    """Handler for the login flow."""

    def __init__(
        self,
        auth_provider: TrustedNetworksAuthProvider,
        ip_addr: IPAddress,
        available_users: dict[str, str | None],
        allow_bypass_login: bool,
    ) -> None:
        """Initialize the login flow."""
        super().__init__(auth_provider)
        self._available_users = available_users
        self._ip_address = ip_addr
        self._allow_bypass_login = allow_bypass_login

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle the step of the form."""
        try:
            cast(
                TrustedNetworksAuthProvider, self._auth_provider
            ).async_validate_access(self._ip_address)

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
            data_schema=vol.Schema({"user": vol.In(self._available_users)}),
        )
