"""Home Assistant auth provider."""
import base64
from collections import OrderedDict
import hashlib
import hmac
from typing import Any, Dict, List, Optional, cast

import bcrypt
import voluptuous as vol

from homeassistant.const import CONF_ID
from homeassistant.core import callback, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util.async_ import run_coroutine_threadsafe

from . import AuthProvider, AUTH_PROVIDER_SCHEMA, AUTH_PROVIDERS, LoginFlow

from ..models import Credentials, UserMeta
from ..util import generate_secret


STORAGE_VERSION = 1
STORAGE_KEY = 'auth_provider.homeassistant'


def _disallow_id(conf: Dict[str, Any]) -> Dict[str, Any]:
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

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the user data store."""
        self.hass = hass
        self._store = hass.helpers.storage.Store(STORAGE_VERSION, STORAGE_KEY)
        self._data = None  # type: Optional[Dict[str, Any]]

    async def async_load(self) -> None:
        """Load stored data."""
        data = await self._store.async_load()

        if data is None:
            data = {
                'salt': generate_secret(),
                'users': []
            }

        self._data = data

    @property
    def users(self) -> List[Dict[str, str]]:
        """Return users."""
        return self._data['users']  # type: ignore

    def validate_login(self, username: str, password: str) -> None:
        """Validate a username and password.

        Raises InvalidAuth if auth invalid.
        """
        dummy = b'$2b$12$CiuFGszHx9eNHxPuQcwBWez4CwDTOcLTX5CbOpV6gef2nYuXkY7BO'
        found = None

        # Compare all users to avoid timing attacks.
        for user in self.users:
            if username == user['username']:
                found = user

        if found is None:
            # check a hash to make timing the same as if user was found
            bcrypt.checkpw(b'foo',
                           dummy)
            raise InvalidAuth

        user_hash = base64.b64decode(found['password'])

        # if the hash is not a bcrypt hash...
        # provide a transparant upgrade for old pbkdf2 hash format
        if not (user_hash.startswith(b'$2a$')
                or user_hash.startswith(b'$2b$')
                or user_hash.startswith(b'$2x$')
                or user_hash.startswith(b'$2y$')):
            # IMPORTANT! validate the login, bail if invalid
            hashed = self.legacy_hash_password(password)
            if not hmac.compare_digest(hashed, user_hash):
                raise InvalidAuth
            # then re-hash the valid password with bcrypt
            self.change_password(found['username'], password)
            run_coroutine_threadsafe(
                self.async_save(), self.hass.loop
            ).result()
            user_hash = base64.b64decode(found['password'])

        # bcrypt.checkpw is timing-safe
        if not bcrypt.checkpw(password.encode(),
                              user_hash):
            raise InvalidAuth

    def legacy_hash_password(self, password: str,
                             for_storage: bool = False) -> bytes:
        """LEGACY password encoding."""
        # We're no longer storing salts in data, but if one exists we
        # should be able to retrieve it.
        salt = self._data['salt'].encode()  # type: ignore
        hashed = hashlib.pbkdf2_hmac('sha512', password.encode(), salt, 100000)
        if for_storage:
            hashed = base64.b64encode(hashed)
        return hashed

    # pylint: disable=no-self-use
    def hash_password(self, password: str, for_storage: bool = False) -> bytes:
        """Encode a password."""
        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)) \
            # type: bytes
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

    async def async_save(self) -> None:
        """Save data."""
        await self._store.async_save(self._data)


@AUTH_PROVIDERS.register('homeassistant')
class HassAuthProvider(AuthProvider):
    """Auth provider based on a local storage of users in HASS config dir."""

    DEFAULT_TITLE = 'Home Assistant Local'

    data = None

    async def async_initialize(self) -> None:
        """Initialize the auth provider."""
        if self.data is not None:
            return

        self.data = Data(self.hass)
        await self.data.async_load()

    async def async_login_flow(
            self, context: Optional[Dict]) -> LoginFlow:
        """Return a flow to login."""
        return HassLoginFlow(self)

    async def async_validate_login(self, username: str, password: str) -> None:
        """Validate a username and password."""
        if self.data is None:
            await self.async_initialize()
            assert self.data is not None

        await self.hass.async_add_executor_job(
            self.data.validate_login, username, password)

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
        """Get extra info for this credential."""
        return UserMeta(name=credentials.data['username'], is_active=True)

    async def async_will_remove_credentials(
            self, credentials: Credentials) -> None:
        """When credentials get removed, also remove the auth."""
        if self.data is None:
            await self.async_initialize()
            assert self.data is not None

        try:
            self.data.async_remove_auth(credentials.data['username'])
            await self.data.async_save()
        except InvalidUser:
            # Can happen if somehow we didn't clean up a credential
            pass


class HassLoginFlow(LoginFlow):
    """Handler for the login flow."""

    async def async_step_init(
            self, user_input: Optional[Dict[str, str]] = None) \
            -> Dict[str, Any]:
        """Handle the step of the form."""
        errors = {}

        if user_input is not None:
            try:
                await cast(HassAuthProvider, self._auth_provider)\
                    .async_validate_login(user_input['username'],
                                          user_input['password'])
            except InvalidAuth:
                errors['base'] = 'invalid_auth'

            if not errors:
                user_input.pop('password')
                return await self.async_finish(user_input)

        schema = OrderedDict()  # type: Dict[str, type]
        schema['username'] = str
        schema['password'] = str

        return self.async_show_form(
            step_id='init',
            data_schema=vol.Schema(schema),
            errors=errors,
        )
