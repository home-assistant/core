"""
Support Legacy API password auth provider.

It will be removed when auth system production ready
"""
import hmac
from typing import Any, Dict, Optional, cast, TYPE_CHECKING

import voluptuous as vol

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError

from . import AuthProvider, AUTH_PROVIDER_SCHEMA, AUTH_PROVIDERS, LoginFlow
from .. import AuthManager
from ..models import Credentials, UserMeta, User

if TYPE_CHECKING:
    from homeassistant.components.http import HomeAssistantHTTP  # noqa: F401


USER_SCHEMA = vol.Schema({
    vol.Required('username'): str,
})


CONFIG_SCHEMA = AUTH_PROVIDER_SCHEMA.extend({
}, extra=vol.PREVENT_EXTRA)

LEGACY_USER_NAME = 'Legacy API password user'


class InvalidAuthError(HomeAssistantError):
    """Raised when submitting invalid authentication."""


async def async_get_user(hass: HomeAssistant) -> User:
    """Return the legacy API password user."""
    auth = cast(AuthManager, hass.auth)  # type: ignore
    found = None

    for prv in auth.auth_providers:
        if prv.type == 'legacy_api_password':
            found = prv
            break

    if found is None:
        raise ValueError('Legacy API password provider not found')

    return await auth.async_get_or_create_user(
        await found.async_get_or_create_credentials({})
    )


@AUTH_PROVIDERS.register('legacy_api_password')
class LegacyApiPasswordAuthProvider(AuthProvider):
    """Example auth provider based on hardcoded usernames and passwords."""

    DEFAULT_TITLE = 'Legacy API Password'

    async def async_login_flow(self, context: Optional[Dict]) -> LoginFlow:
        """Return a flow to login."""
        return LegacyLoginFlow(self)

    @callback
    def async_validate_login(self, password: str) -> None:
        """Validate a username and password."""
        hass_http = getattr(self.hass, 'http', None)  # type: HomeAssistantHTTP

        if not hmac.compare_digest(hass_http.api_password.encode('utf-8'),
                                   password.encode('utf-8')):
            raise InvalidAuthError

    async def async_get_or_create_credentials(
            self, flow_result: Dict[str, str]) -> Credentials:
        """Return credentials for this login."""
        credentials = await self.async_credentials()
        if credentials:
            return credentials[0]

        return self.async_create_credentials({})

    async def async_user_meta_for_credentials(
            self, credentials: Credentials) -> UserMeta:
        """
        Return info for the user.

        Will be used to populate info when creating a new user.
        """
        return UserMeta(name=LEGACY_USER_NAME, is_active=True)


class LegacyLoginFlow(LoginFlow):
    """Handler for the login flow."""

    async def async_step_init(
            self, user_input: Optional[Dict[str, str]] = None) \
            -> Dict[str, Any]:
        """Handle the step of the form."""
        errors = {}

        hass_http = getattr(self.hass, 'http', None)
        if hass_http is None or not hass_http.api_password:
            return self.async_abort(
                reason='no_api_password_set'
            )

        if user_input is not None:
            try:
                cast(LegacyApiPasswordAuthProvider, self._auth_provider)\
                    .async_validate_login(user_input['password'])
            except InvalidAuthError:
                errors['base'] = 'invalid_auth'

            if not errors:
                return await self.async_finish({})

        return self.async_show_form(
            step_id='init',
            data_schema=vol.Schema({'password': str}),
            errors=errors,
        )
