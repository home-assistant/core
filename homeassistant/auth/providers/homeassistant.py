"""Home Assistant auth provider."""
import base64
from collections import OrderedDict
import hashlib
import hmac
from typing import Dict  # noqa: F401 pylint: disable=unused-import

import voluptuous as vol

from homeassistant import data_entry_flow
from homeassistant.const import CONF_ID
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError

from homeassistant.auth.util import generate_secret

from . import AuthProvider, AUTH_PROVIDER_SCHEMA, AUTH_PROVIDERS

STORAGE_VERSION = 1
STORAGE_KEY = 'auth_provider.homeassistant'


def _disallow_id(conf):
    """Disallow ID in config."""
    if CONF_ID in conf:
        raise vol.Invalid(
            'ID is not allowed for the homeassistant auth provider.')

    return conf


CONFIG_SCHEMA = vol.All(AUTH_PROVIDER_SCHEMA, _disallow_id)


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
                'salt': generate_secret(),
                'users': []
            }

        self._data = data

    @property
    def users(self):
        """Return users."""
        return self._data['users']

    def validate_login(self, username: str, password: str) -> None:
        """Validate a username and password.

        Raises InvalidAuth if auth invalid.
        """
        hashed = self.hash_password(password)

        found = None

        # Compare all users to avoid timing attacks.
        for user in self._data['users']:
            if username == user['username']:
                found = user

        if found is None:
            # Do one more compare to make timing the same as if user was found.
            hmac.compare_digest(hashed, hashed)
            raise InvalidAuth

        if not hmac.compare_digest(hashed,
                                   base64.b64decode(found['password'])):
            raise InvalidAuth

    def hash_password(self, password: str, for_storage: bool = False) -> bytes:
        """Encode a password."""
        hashed = hashlib.pbkdf2_hmac(
            'sha512', password.encode(), self._data['salt'].encode(), 100000)
        if for_storage:
            hashed = base64.b64encode(hashed)
        return hashed

    def add_auth(self, username: str, password: str) -> None:
        """Add a new authenticated user/pass."""
        if any(user['username'] == username for user in self.users):
            raise InvalidUser

        self.users.append({
            'username': username,
            'password': self.hash_password(password, True).decode(),
        })

    @callback
    def async_remove_auth(self, username: str) -> None:
        """Remove authentication."""
        index = None
        for i, user in enumerate(self.users):
            if user['username'] == username:
                index = i
                break

        if index is None:
            raise InvalidUser

        self.users.pop(index)

    def change_password(self, username: str, new_password: str) -> None:
        """Update the password.

        Raises InvalidUser if user cannot be found.
        """
        for user in self.users:
            if user['username'] == username:
                user['password'] = self.hash_password(
                    new_password, True).decode()
                break
        else:
            raise InvalidUser

    async def async_save(self):
        """Save data."""
        await self._store.async_save(self._data)


@AUTH_PROVIDERS.register('homeassistant')
class HassAuthProvider(AuthProvider):
    """Auth provider based on a local storage of users in HASS config dir."""

    DEFAULT_TITLE = 'Home Assistant Local'

    data = None

    async def async_initialize(self):
        """Initialize the auth provider."""
        if self.data is not None:
            return

        self.data = Data(self.hass)
        await self.data.async_load()

    async def async_credential_flow(self):
        """Return a flow to login."""
        return LoginFlow(self)

    async def async_validate_login(self, username: str, password: str):
        """Helper to validate a username and password."""
        if self.data is None:
            await self.async_initialize()

        await self.hass.async_add_executor_job(
            self.data.validate_login, username, password)

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

    async def async_user_meta_for_credentials(self, credentials):
        """Get extra info for this credential."""
        return {
            'name': credentials.data['username'],
            'is_active': True,
        }

    async def async_will_remove_credentials(self, credentials):
        """When credentials get removed, also remove the auth."""
        if self.data is None:
            await self.async_initialize()

        try:
            self.data.async_remove_auth(credentials.data['username'])
            await self.data.async_save()
        except InvalidUser:
            # Can happen if somehow we didn't clean up a credential
            pass


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

        schema = OrderedDict()  # type: Dict[str, type]
        schema['username'] = str
        schema['password'] = str

        return self.async_show_form(
            step_id='init',
            data_schema=vol.Schema(schema),
            errors=errors,
        )
