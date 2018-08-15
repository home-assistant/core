"""Example auth provider."""
from collections import OrderedDict
import hmac
from typing import Any, Dict, Optional

import voluptuous as vol

from homeassistant.exceptions import HomeAssistantError
from homeassistant import data_entry_flow
from homeassistant.core import callback

from . import AuthProvider, AUTH_PROVIDER_SCHEMA, AUTH_PROVIDERS
from ..models import Credentials, UserMeta


USER_SCHEMA = vol.Schema({
    vol.Required('username'): str,
    vol.Required('password'): str,
    vol.Optional('name'): str,
})


CONFIG_SCHEMA = AUTH_PROVIDER_SCHEMA.extend({
    vol.Required('users'): [USER_SCHEMA]
}, extra=vol.PREVENT_EXTRA)


class InvalidAuthError(HomeAssistantError):
    """Raised when submitting invalid authentication."""


@AUTH_PROVIDERS.register('insecure_example')
class ExampleAuthProvider(AuthProvider):
    """Example auth provider based on hardcoded usernames and passwords."""

    async def async_credential_flow(
            self, context: Optional[Dict]) -> 'LoginFlow':
        """Return a flow to login."""
        return LoginFlow(self)

    @callback
    def async_validate_login(self, username: str, password: str) -> None:
        """Helper to validate a username and password."""
        user = None

        # Compare all users to avoid timing attacks.
        for usr in self.config['users']:
            if hmac.compare_digest(username.encode('utf-8'),
                                   usr['username'].encode('utf-8')):
                user = usr

        if user is None:
            # Do one more compare to make timing the same as if user was found.
            hmac.compare_digest(password.encode('utf-8'),
                                password.encode('utf-8'))
            raise InvalidAuthError

        if not hmac.compare_digest(user['password'].encode('utf-8'),
                                   password.encode('utf-8')):
            raise InvalidAuthError

    async def async_get_or_create_credentials(
            self, flow_result: Dict[str, str]) -> Credentials:
        """Get credentials based on the flow result."""
        username = flow_result['username']

        for credential in await self.async_credentials():
            if credential.data['username'] == username:
                return credential

        # Create new credentials.
        return self.async_create_credentials({
            'username': username
        })

    async def async_user_meta_for_credentials(
            self, credentials: Credentials) -> UserMeta:
        """Return extra user metadata for credentials.

        Will be used to populate info when creating a new user.
        """
        username = credentials.data['username']
        name = None

        for user in self.config['users']:
            if user['username'] == username:
                name = user.get('name')
                break

        return UserMeta(name=name, is_active=True)


class LoginFlow(data_entry_flow.FlowHandler):
    """Handler for the login flow."""

    def __init__(self, auth_provider: ExampleAuthProvider) -> None:
        """Initialize the login flow."""
        self._auth_provider = auth_provider

    async def async_step_init(
            self, user_input: Dict[str, str] = None) -> Dict[str, Any]:
        """Handle the step of the form."""
        errors = {}

        if user_input is not None:
            try:
                self._auth_provider.async_validate_login(
                    user_input['username'], user_input['password'])
            except InvalidAuthError:
                errors['base'] = 'invalid_auth'

            if not errors:
                return self.async_create_entry(
                    title=self._auth_provider.name,
                    data=user_input
                )

        schema = OrderedDict()  # type: Dict[str, type]
        schema['username'] = str
        schema['password'] = str

        return self.async_show_form(
            step_id='init',
            data_schema=vol.Schema(schema),
            errors=errors,
        )
