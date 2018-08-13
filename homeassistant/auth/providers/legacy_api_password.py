"""
Support Legacy API password auth provider.

It will be removed when auth system production ready
"""
from collections import OrderedDict
import hmac

import voluptuous as vol

from homeassistant.exceptions import HomeAssistantError
from homeassistant import data_entry_flow
from homeassistant.core import callback

from . import AuthProvider, AUTH_PROVIDER_SCHEMA, AUTH_PROVIDERS


USER_SCHEMA = vol.Schema({
    vol.Required('username'): str,
})


CONFIG_SCHEMA = AUTH_PROVIDER_SCHEMA.extend({
}, extra=vol.PREVENT_EXTRA)

LEGACY_USER = 'homeassistant'


class InvalidAuthError(HomeAssistantError):
    """Raised when submitting invalid authentication."""


@AUTH_PROVIDERS.register('legacy_api_password')
class LegacyApiPasswordAuthProvider(AuthProvider):
    """Example auth provider based on hardcoded usernames and passwords."""

    DEFAULT_TITLE = 'Legacy API Password'

    async def async_credential_flow(self, context):
        """Return a flow to login."""
        return LoginFlow(self)

    @callback
    def async_validate_login(self, password):
        """Helper to validate a username and password."""
        if not hasattr(self.hass, 'http'):
            raise ValueError('http component is not loaded')

        if self.hass.http.api_password is None:
            raise ValueError('http component is not configured using'
                             ' api_password')

        if not hmac.compare_digest(self.hass.http.api_password.encode('utf-8'),
                                   password.encode('utf-8')):
            raise InvalidAuthError

    async def async_get_or_create_credentials(self, flow_result):
        """Return LEGACY_USER always."""
        for credential in await self.async_credentials():
            if credential.data['username'] == LEGACY_USER:
                return credential

        return self.async_create_credentials({
            'username': LEGACY_USER
        })

    async def async_user_meta_for_credentials(self, credentials):
        """
        Set name as LEGACY_USER always.

        Will be used to populate info when creating a new user.
        """
        return {
            'name': LEGACY_USER,
            'is_active': True,
        }


class LoginFlow(data_entry_flow.FlowHandler):
    """Handler for the login flow."""

    def __init__(self, auth_provider):
        """Initialize the login flow."""
        self._auth_provider = auth_provider

    async def async_step_init(self, user_input=None):
        """Handle the step of the form."""
        errors = {}

        if user_input is not None:
            try:
                self._auth_provider.async_validate_login(
                    user_input['password'])
            except InvalidAuthError:
                errors['base'] = 'invalid_auth'

            if not errors:
                return self.async_create_entry(
                    title=self._auth_provider.name,
                    data={}
                )

        schema = OrderedDict()
        schema['password'] = str

        return self.async_show_form(
            step_id='init',
            data_schema=vol.Schema(schema),
            errors=errors,
        )
