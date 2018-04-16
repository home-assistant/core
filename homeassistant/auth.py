"""Provide an authentication layer for Home Assistant."""
import asyncio
from datetime import datetime
import logging
import uuid

import attr
import voluptuous as vol
from voluptuous.humanize import humanize_error

from homeassistant import data_entry_flow
from homeassistant.core import callback
from homeassistant.const import CONF_TYPE, CONF_NAME, CONF_ID
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util.decorator import Registry
from homeassistant.util import dt as dt_util


_LOGGER = logging.getLogger(__name__)


AUTH_PROVIDERS = Registry()

AUTH_PROVIDER_SCHEMA = vol.Schema({
    vol.Required(CONF_TYPE): str,
    vol.Optional(CONF_NAME): str,
    # Specify ID if you have two auth providers for same type.
    vol.Optional(CONF_ID): str,
})


class AuthError(HomeAssistantError):
    """Generic authentication error."""


class InvalidUser(AuthError):
    """Raised when an invalid user has been specified."""


class InvalidPassword(AuthError):
    """Raised when an invalid password has been supplied."""


class UnknownError(AuthError):
    """When an unknown error occurs."""


class AuthProvider:
    """Provider of user authentication."""

    DEFAULT_TITLE = 'Unnamed auth provider'

    def __init__(self, store, config):
        """Initialize an auth provider."""
        self.store = store
        self.config = config

    @property
    def id(self):
        """Return id of the auth provider.

        Optional, can be None.
        """
        return self.config.get(CONF_ID)

    @property
    def type(self):
        """Return type of the provider."""
        return self.config[CONF_TYPE]

    @property
    def name(self):
        """Return the name of the auth provider."""
        return self.config.get(CONF_NAME, self.DEFAULT_TITLE)

    async def async_credentials(self):
        """Return all credentials of this provider."""
        return await self.store.credentials_for_provider(self.type, self.id)

    # Implement by extending class

    async def async_initialize(self):
        """Initialize the auth provider."""

    async def async_credential_flow(self):
        """Return the data flow for logging in with auth provider."""
        raise NotImplementedError

    async def async_get_or_create_credentials(self, flow_result):
        """Get credentials based on the flow result."""
        raise NotImplementedError

    async def async_user_meta_for_credentials(self, credentials):
        """Return extra user metadata for credentials.

        Will be used to populate info when creating a new user.
        """
        return {}

    @callback
    def async_create_credentials(self, data):
        """Create credentials."""
        return Credentials(
            auth_provider_type=self.type,
            auth_provider_id=self.id,
            data=data,
        )

    # async def async_register_flow(self):
    #     """Return the data flow for registering with the auth provider."""
    #     raise NotImplementedError

    # async def async_register(self, flow_result):
    #     """Create a new user and return credentials."""
    #     raise NotImplementedError

    # async def async_change_password(self, credentials, new_password):
    #     """Change the password of a user."""
    #     raise NotImplementedError


@attr.s(slots=True)
class User:
    """A user."""

    id = attr.ib(type=uuid.UUID, default=None)
    is_owner = attr.ib(type=bool, default=False)
    is_active = attr.ib(type=bool, default=False)
    name = attr.ib(type=str, default=None)
    # Minimum time a token has to be issued to be considered valid.
    # When a user clicks "log out all sessions", we update this timestamp.
    token_min_issued = attr.ib(type=datetime,
                               default=attr.Factory(dt_util.utcnow))
    # List of credentials of a user.
    credentials = attr.ib(type=list, default=attr.Factory(list))

    def as_dict(self):
        """Convert user object to a dictionary."""
        return {
            'id': self.id,
            'is_owner': self.is_owner,
            'is_active': self.is_active,
            'name': self.name,
        }


@attr.s(slots=True)
class Credentials:
    """Credentials for a user on an auth provider."""

    auth_provider_type = attr.ib(type=str)
    auth_provider_id = attr.ib(type=str)

    # Allow the auth provider to store data to represent their auth.
    data = attr.ib(type=dict)

    id = attr.ib(type=uuid.UUID, default=None)


@attr.s(slots=True)
class Client:
    """Client that interacts with Home Assistant on behalf of a user."""

    id = attr.ib(type=uuid.UUID)
    secret = attr.ib(type=str)


@callback
def load_auth_provider_module(provider):
    """Load an auth provider."""
    # Stub.
    from .auth_providers import insecure_example
    return insecure_example


async def auth_manager_from_config(hass, provider_configs):
    """Initialize an auth manager from config."""
    store = AuthStore()
    providers = await asyncio.gather(
        *[_auth_provider_from_config(store, config)
          for config in provider_configs])
    provider_hash = {}
    for provider in providers:
        if provider is None:
            continue

        key = (provider.type, provider.id)

        if key in provider_hash:
            _LOGGER.error(
                'Found duplicate provider: %s. Please add unique IDs if you '
                'want to have the same provider twice.', key)
            continue

        provider_hash[key] = provider
    manager = AuthManager(hass, store, provider_hash)
    await manager.initialize()
    return manager


async def _auth_provider_from_config(store, config):
    """Initialize an auth provider from a config."""
    provider_name = config[CONF_TYPE]
    module = load_auth_provider_module(provider_name)

    try:
        config = module.CONFIG_SCHEMA(config)
    except vol.Invalid as err:
        _LOGGER.error('Invalid configuration for auth provider %s: %s',
                      provider_name, humanize_error(config, err))
        return None

    return AUTH_PROVIDERS[provider_name](store, config)


class AuthManager:
    """Manage the authentication for Home Assistant."""

    def __init__(self, hass, store, providers):
        """Initialize the auth manager."""
        self._store = store
        self._providers = providers
        self.login_flow = data_entry_flow.FlowManager(
            hass, self._async_create_login_flow,
            self._async_finish_login_flow)
        self._flow_credentials = {}

    async def initialize(self):
        """Initialize the auth manager."""
        if not self._providers:
            return
        await asyncio.wait([provider.async_initialize() for provider
                            in self._providers.values()])

    @callback
    def async_auth_providers(self):
        """Return a list of available auth providers."""
        return [{
            'name': provider.name,
            'id': provider.id,
            'type': provider.type,
        } for provider in self._providers.values()]

    async def async_get_user(self, user_id):
        """Retrieve a user."""
        return await self._store.async_get_user(user_id)

    async def async_get_or_create_user(self, credentials):
        """Get or create a user."""
        return await self._store.async_get_or_create_user(
            credentials, self._async_get_auth_provider(credentials))

    async def link_user(self, user, credentials):
        """Link credentials to an existing user."""
        await self._store.async_link_user(user, credentials)

    async def _async_create_login_flow(self, handler):
        """Create a login flow."""
        auth_provider = self._providers[handler]
        return await auth_provider.async_credential_flow()

    async def _async_finish_login_flow(self, result):
        """Result of a credential login flow."""
        provider = self._providers[result['handler']]
        return await provider.async_get_or_create_credentials(result['data'])

    @callback
    def _async_get_auth_provider(self, credentials):
        """Helper to get auth provider from a set of credentials."""
        auth_provider_key = (credentials.auth_provider_type,
                             credentials.auth_provider_id)
        return self._providers[auth_provider_key]


class AuthStore:
    """Stores authentication info.

    Any mutation to an object should happen inside the auth store.

    The auth store is lazy. It won't load the data from disk until a method is
    called that needs it.
    """

    def __init__(self):
        """Initialize the auth store."""
        self.users = None

    async def credentials_for_provider(self, provider_type, provider_id):
        """Return credentials for specific auth provider type and id."""
        if self.users is None:
            await self.async_load()

        result = []

        for user in self.users:
            for credentials in user.credentials:
                if (credentials.auth_provider_type == provider_type and
                        credentials.auth_provider_id == provider_id):
                    result.append(credentials)

        return result

    async def async_get_user(self, user_id):
        """Retrieve a user."""
        if self.users is None:
            await self.async_load()

        for user in self.users:
            if user.id == user_id:
                return user

        return None

    async def async_get_or_create_user(self, credentials, auth_provider):
        """Get or create a new user for given credentials.

        If link_user is passed in, the credentials will be linked to the passed
        in user if the credentials are new.
        """
        if self.users is None:
            await self.async_load()

        # New credentials, store in user
        if credentials.id is None:
            info = await auth_provider.async_user_meta_for_credentials(
                credentials)
            # Make owner and activate user if it's the first user.
            if self.users:
                is_owner = False
                is_active = False
            else:
                is_owner = True
                is_active = True

            new_user = User(
                is_owner=is_owner,
                is_active=is_active,
                name=info.get('name'),
            )
            self.users.append(new_user)
            await self.async_link_user(new_user, credentials)
            return new_user

        for user in self.users:
            for creds in user.credentials:
                if (creds.auth_provider_type == credentials.auth_provider_type
                        and creds.auth_provider_id == creds.auth_provider_id):
                    return user

        raise ValueError('We got credentials with ID but found no user')

    async def async_link_user(self, user, credentials):
        """Add credentials to an existing user."""
        user.credentials.append(credentials)
        await self.async_save()

    async def async_load(self):
        """Load the users."""
        # TODO load from disk
        self.users = []

    async def async_save(self):
        """Save users."""
        # Set IDs for unsaved users & credentials
        for user in self.users:
            if user.id is None:
                user.id = uuid.uuid4().hex

            for credentials in user.credentials:
                if credentials.id is None:
                    credentials.id = uuid.uuid4().hex

        # TODO store to disk
