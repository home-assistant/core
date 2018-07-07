"""Home Assistant auth provider."""
import base64
from collections import OrderedDict
import hashlib
import hmac

import voluptuous as vol

from homeassistant import auth, data_entry_flow
from homeassistant.exceptions import HomeAssistantError


STORAGE_VERSION = 1
STORAGE_KEY = 'auth_provider.homeassistant'

CONFIG_SCHEMA = auth.AUTH_PROVIDER_SCHEMA.extend({
}, extra=vol.PREVENT_EXTRA)


class InvalidAuth(HomeAssistantError):
    """Raised when we encounter invalid authentication."""


class InvalidUser(HomeAssistantError):
    """Raised when invalid user is specified.

    Will not be raised when validating authentication.
    """


class Data:
    """Hold the user data."""

    def __init__(self, hass):
        """Initialize the user data store."""
        self.hass = hass
        self._store = hass.helpers.storage.Store(STORAGE_VERSION, STORAGE_KEY)
        self._data = None

    async def async_load(self):
        """Load stored data."""
        data = await self._store.async_load()

        if data is None:
            data = {
                'salt': auth.generate_secret(),
                'users': []
            }

        self._data = data

    @property
    def users(self):
        """Return users."""
        return self._data['users']

    def validate_login(self, username, password):
        """Validate a username and password.

        Raises InvalidAuth if auth invalid.
        """
        password = self.hash_password(password)

        found = None

        # Compare all users to avoid timing attacks.
        for user in self._data['users']:
            if username == user['username']:
                found = user

        if found is None:
            # Do one more compare to make timing the same as if user was found.
            hmac.compare_digest(password, password)
            raise InvalidAuth

        if not hmac.compare_digest(password,
                                   base64.b64decode(found['password'])):
            raise InvalidAuth

    def hash_password(self, password, for_storage=False):
        """Encode a password."""
        hashed = hashlib.pbkdf2_hmac(
            'sha512', password.encode(), self._data['salt'].encode(), 100000)
        if for_storage:
            hashed = base64.b64encode(hashed).decode()
        return hashed

    def add_user(self, username, password):
        """Add a user."""
        if any(user['username'] == username for user in self.users):
            raise InvalidUser

        self.users.append({
            'username': username,
            'password': self.hash_password(password, True),
        })

    def change_password(self, username, new_password):
        """Update the password of a user.

        Raises InvalidUser if user cannot be found.
        """
        for user in self.users:
            if user['username'] == username:
                user['password'] = self.hash_password(new_password, True)
                break
        else:
            raise InvalidUser

    async def async_save(self):
        """Save data."""
        await self._store.async_save(self._data)


@auth.AUTH_PROVIDERS.register('homeassistant')
class HassAuthProvider(auth.AuthProvider):
    """Auth provider based on a local storage of users in HASS config dir."""

    DEFAULT_TITLE = 'Home Assistant Local'

    async def async_credential_flow(self):
        """Return a flow to login."""
        return LoginFlow(self)

    async def async_validate_login(self, username, password):
        """Helper to validate a username and password."""
        data = Data(self.hass)
        await data.async_load()
        await self.hass.async_add_executor_job(
            data.validate_login, username, password)

    async def async_get_or_create_credentials(self, flow_result):
        """Get credentials based on the flow result."""
        username = flow_result['username']

        for credential in await self.async_credentials():
            if credential.data['username'] == username:
                return credential

        # Create new credentials.
        return self.async_create_credentials({
            'username': username
        })


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
                await self._auth_provider.async_validate_login(
                    user_input['username'], user_input['password'])
            except InvalidAuth:
                errors['base'] = 'invalid_auth'

            if not errors:
                return self.async_create_entry(
                    title=self._auth_provider.name,
                    data=user_input
                )

        schema = OrderedDict()
        schema['username'] = str
        schema['password'] = str

        return self.async_show_form(
            step_id='init',
            data_schema=vol.Schema(schema),
            errors=errors,
        )
