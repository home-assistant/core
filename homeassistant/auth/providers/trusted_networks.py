"""Trusted Networks auth provider.

It shows list of users if access from trusted network.
Abort login flow if not access from trusted network.
"""
from typing import Any, Dict, Optional, cast

import voluptuous as vol

from homeassistant.components.http import HomeAssistantHTTP  # noqa: F401
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError

from . import AuthProvider, AUTH_PROVIDER_SCHEMA, AUTH_PROVIDERS, LoginFlow
from ..models import Credentials, UserMeta

CONFIG_SCHEMA = AUTH_PROVIDER_SCHEMA.extend({
}, extra=vol.PREVENT_EXTRA)


class InvalidAuthError(HomeAssistantError):
    """Raised when try to access from untrusted networks."""


class InvalidUserError(HomeAssistantError):
    """Raised when try to login as invalid user."""


@AUTH_PROVIDERS.register('trusted_networks')
class TrustedNetworksAuthProvider(AuthProvider):
    """Trusted Networks auth provider.

    Allow passwordless access from trusted network.
    """

    DEFAULT_TITLE = 'Trusted Networks'

    @property
    def support_mfa(self) -> bool:
        """Trusted Networks auth provider does not support MFA."""
        return False

    async def async_login_flow(self, context: Optional[Dict]) -> LoginFlow:
        """Return a flow to login."""
        assert context is not None
        users = await self.store.async_get_users()
        available_users = {user.id: user.name
                           for user in users
                           if not user.system_generated and user.is_active}

        return TrustedNetworksLoginFlow(
            self, cast(str, context.get('ip_address')), available_users)

    async def async_get_or_create_credentials(
            self, flow_result: Dict[str, str]) -> Credentials:
        """Get credentials based on the flow result."""
        user_id = flow_result['user']

        users = await self.store.async_get_users()
        for user in users:
            if (not user.system_generated and
                    user.is_active and
                    user.id == user_id):
                for credential in await self.async_credentials():
                    if credential.data['user_id'] == user_id:
                        return credential
                cred = self.async_create_credentials({'user_id': user_id})
                await self.store.async_link_user(user, cred)
                return cred

        # We only allow login as exist user
        raise InvalidUserError

    async def async_user_meta_for_credentials(
            self, credentials: Credentials) -> UserMeta:
        """Return extra user metadata for credentials.

        Trusted network auth provider should never create new user.
        """
        raise NotImplementedError

    @callback
    def async_validate_access(self, ip_address: str) -> None:
        """Make sure the access from trusted networks.

        Raise InvalidAuthError if not.
        Raise InvalidAuthError if trusted_networks is not configured.
        """
        hass_http = getattr(self.hass, 'http', None)  # type: HomeAssistantHTTP

        if not hass_http or not hass_http.trusted_networks:
            raise InvalidAuthError('trusted_networks is not configured')

        if not any(ip_address in trusted_network for trusted_network
                   in hass_http.trusted_networks):
            raise InvalidAuthError('Not in trusted_networks')


class TrustedNetworksLoginFlow(LoginFlow):
    """Handler for the login flow."""

    def __init__(self, auth_provider: TrustedNetworksAuthProvider,
                 ip_address: str, available_users: Dict[str, Optional[str]]) \
            -> None:
        """Initialize the login flow."""
        super().__init__(auth_provider)
        self._available_users = available_users
        self._ip_address = ip_address

    async def async_step_init(
            self, user_input: Optional[Dict[str, str]] = None) \
            -> Dict[str, Any]:
        """Handle the step of the form."""
        try:
            cast(TrustedNetworksAuthProvider, self._auth_provider)\
                .async_validate_access(self._ip_address)

        except InvalidAuthError:
            return self.async_abort(
                reason='not_whitelisted'
            )

        if user_input is not None:
            return await self.async_finish(user_input)

        return self.async_show_form(
            step_id='init',
            data_schema=vol.Schema({'user': vol.In(self._available_users)}),
        )
