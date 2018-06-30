"""Home Assistant auth provider."""
import base64
from collections import OrderedDict
import hashlib
import hmac
import logging
from datetime import timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant import auth, data_entry_flow
from homeassistant.auth import generate_secret
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util

REQUIREMENTS = ['pyotp==2.2.6']

STORAGE_VERSION = 1
STORAGE_KEY = 'auth_provider.homeassistant'

CONF_ENABLE_2FA = 'enable_2fa'

CONFIG_SCHEMA = auth.AUTH_PROVIDER_SCHEMA.extend({
    # NOTE this config enable 2FA for all users
    vol.Optional(CONF_ENABLE_2FA): cv.boolean,
}, extra=vol.PREVENT_EXTRA)


SESSION_TOKEN_EXPIRATION = timedelta(minutes=5)

_LOGGER = logging.getLogger(__name__)


class InvalidAuth(HomeAssistantError):
    """Raised when we encounter invalid authentication."""


class InvalidUser(HomeAssistantError):
    """Raised when invalid user is specified.

    Will not be raised when validating authentication.
    """


class Request2FA(HomeAssistantError):
    """Raised when we need user input Two Factor Authentication code."""

    def __init__(self, session_token):
        """Set session_token."""
        super().__init__()
        self.session_token = session_token


class Data:
    """Hold the user data."""

    def __init__(self, hass, enable_2fa=False):
        """Initialize the user data store."""
        self.hass = hass
        self._store = hass.helpers.storage.Store(STORAGE_VERSION, STORAGE_KEY)
        self._data = None
        self._enable_2fa = enable_2fa

    async def async_load(self):
        """Load stored data."""
        data = await self._store.async_load()

        if data is None:
            data = {
                'salt': auth.generate_secret(),
                'users': [],
                'sessions': {}
            }

        if 'users' not in data:
            data['users'] = []

        if 'sessions' not in data:
            data['sessions'] = {}

        self._data = data

    @property
    def users(self):
        """Return users."""
        return self._data['users']

    @property
    def _sessions(self):
        """Return sessions."""
        return self._data['sessions']

    def open_session(self, user):
        """Create a session for 2FA."""
        # first clean up expired sessions
        self.cleanup_session()

        session_token = generate_secret(64)
        expire_time = dt_util.utcnow() + SESSION_TOKEN_EXPIRATION
        self._sessions[session_token] = (user, expire_time.isoformat())
        return session_token

    def close_session(self, session_token):
        """Close a session for 2FA."""
        user = None
        session = self._sessions.get(session_token)
        if session is not None:
            user = session[0]
            del self._sessions[session_token]
        # clean up expired sessions
        self.cleanup_session()
        return user

    def get_session(self, session_token):
        """Find a session for 2FA."""
        # first clean up expired sessions
        self.cleanup_session()

        return self._sessions.get(session_token)

    def cleanup_session(self):
        """Clean up expired sessions."""
        for session_token in list(self._sessions.keys()):
            _, expire_time = self._sessions[session_token]
            if dt_util.utcnow() > dt_util.parse_datetime(expire_time):
                del self._sessions[session_token]

    def validate_login(self, username, password):
        """Validate a username and password.

        Raises InvalidAuth if auth invalid.
        """
        password = self.hash_password(password)

        found = None

        # Compare all users to avoid timing attacks.
        for user in self.users:
            if username == user['username']:
                found = user

        if found is None:
            # Do one more compare to make timing the same as if user was found.
            hmac.compare_digest(password, password)
            raise InvalidAuth

        if not hmac.compare_digest(password,
                                   base64.b64decode(found['password'])):
            raise InvalidAuth

        if self._enable_2fa:
            if found.get('ota_secret') is None:
                _LOGGER.warning("Although two factor authentication is enabled"
                                " user %s dose not setup accordingly. Ignore"
                                " two factor authentication.",
                                found['username'])
                return
            session_token = self.open_session(found['username'])
            raise Request2FA(session_token)

    def validate_2fa(self, session_token, code):
        """Validate two factor authentication code.

        Raises InvalidAuth if auth invalid.
        """
        import pyotp

        found = self.get_session(session_token)

        ota_secret = None
        if found is not None:
            username, expire_time = found
            for user in self.users:
                if username == user['username']:
                    # double check expire_time
                    if dt_util.utcnow() < dt_util.parse_datetime(expire_time):
                        ota_secret = user['ota_secret']
                    break

        if ota_secret is None:
            # even we cannot find user or session, we still do verify
            # to make timing the same as if session was found.
            pyotp.TOTP(pyotp.random_base32()).verify(code)
            raise InvalidAuth

        ota = pyotp.TOTP(ota_secret)
        if not ota.verify(code):
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
        import pyotp

        if any(user['username'] == username for user in self.users):
            raise InvalidUser

        ota_secret = pyotp.random_base32() if self._enable_2fa else None

        self.users.append({
            'username': username,
            'password': self.hash_password(password, True),
            'ota_secret': ota_secret
        })
        return ota_secret

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
        data = Data(self.hass, self.config.get(CONF_ENABLE_2FA))
        await data.async_load()
        try:
            await self.hass.async_add_executor_job(
                data.validate_login, username, password)
        finally:
            await data.async_save()

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

    async def async_validate_2fa(self, session_token, code):
        """Helper to validate a two factor authentication code."""
        data = Data(self.hass, self.config.get(CONF_ENABLE_2FA))
        await data.async_load()
        try:
            await self.hass.async_add_executor_job(
                data.validate_2fa, session_token, code)
            username = data.close_session(session_token)
            if username is not None:
                return username
            raise InvalidAuth
        finally:
            await data.async_save()


class LoginFlow(data_entry_flow.FlowHandler):
    """Handler for the login flow."""

    def __init__(self, auth_provider):
        """Initialize the login flow."""
        self._auth_provider = auth_provider
        self._session_token = None
        self._user_name = None

    async def async_step_init(self, user_input=None):
        """Handle the step of the form."""
        errors = {}
        result = None

        if user_input is not None:
            try:
                if self._session_token and 'code' in user_input:
                    username = await self._auth_provider.async_validate_2fa(
                        self._session_token, user_input['code'])
                    result = {'username': username}
                else:
                    await self._auth_provider.async_validate_login(
                        user_input['username'], user_input['password'])
                    result = {'username': user_input['username']}
            except InvalidAuth:
                errors['base'] = 'invalid_auth'
            except Request2FA as request2fa:
                self._session_token = request2fa.session_token
                errors['base'] = 'request_2fa'

            if not errors and result:
                return self.async_create_entry(
                    title=self._auth_provider.name,
                    data=result
                )

        schema = OrderedDict()
        if self._session_token:
            schema['code'] = str
        else:
            schema['username'] = str
            schema['password'] = str

        return self.async_show_form(
            step_id='init',
            data_schema=vol.Schema(schema),
            errors=errors,
        )
