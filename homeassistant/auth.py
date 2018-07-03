"""Provide an authentication layer for Home Assistant."""
import asyncio
import binascii
import importlib
import logging
import os
import uuid
from collections import OrderedDict
from datetime import datetime, timedelta

import attr
import voluptuous as vol
from voluptuous.humanize import humanize_error

from homeassistant import data_entry_flow, requirements
from homeassistant.const import CONF_TYPE, CONF_NAME, CONF_ID
from homeassistant.core import callback
from homeassistant.util import dt as dt_util
from homeassistant.util.decorator import Registry

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1
STORAGE_KEY = 'auth'

AUTH_PROVIDERS = Registry()

AUTH_PROVIDER_SCHEMA = vol.Schema({
    vol.Required(CONF_TYPE): str,
    vol.Optional(CONF_NAME): str,
    # Specify ID if you have two auth providers for same type.
    vol.Optional(CONF_ID): str,
}, extra=vol.ALLOW_EXTRA)

ACCESS_TOKEN_EXPIRATION = timedelta(minutes=30)
DATA_REQS = 'auth_reqs_processed'


def generate_secret(entropy: int = 32) -> str:
    """Generate a secret.

    Backport of secrets.token_hex from Python 3.6

    Event loop friendly.
    """
    return binascii.hexlify(os.urandom(entropy)).decode('ascii')


class AuthProvider:
    """Provider of user authentication."""

    DEFAULT_TITLE = 'Unnamed auth provider'

    initialized = False

    def __init__(self, hass, store, config):
        """Initialize an auth provider."""
        self.hass = hass
        self.store = store
        self.config = config

    @property
    def id(self):  # pylint: disable=invalid-name
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

    @callback
    def async_create_credentials(self, data):
        """Create credentials."""
        return Credentials(
            auth_provider_type=self.type,
            auth_provider_id=self.id,
            data=data,
        )

    # Implement by extending class

    async def async_initialize(self):
        """Initialize the auth provider.

        Optional.
        """

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


@attr.s(slots=True)
class User:
    """A user."""

    id = attr.ib(type=str, default=attr.Factory(lambda: uuid.uuid4().hex))
    is_owner = attr.ib(type=bool, default=False)
    is_active = attr.ib(type=bool, default=False)
    name = attr.ib(type=str, default=None)

    # List of credentials of a user.
    credentials = attr.ib(type=list, default=attr.Factory(list), cmp=False)

    # Tokens associated with a user.
    refresh_tokens = attr.ib(type=dict, default=attr.Factory(dict), cmp=False)


@attr.s(slots=True)
class RefreshToken:
    """RefreshToken for a user to grant new access tokens."""

    user = attr.ib(type=User)
    client_id = attr.ib(type=str)
    id = attr.ib(type=str, default=attr.Factory(lambda: uuid.uuid4().hex))
    created_at = attr.ib(type=datetime, default=attr.Factory(dt_util.utcnow))
    access_token_expiration = attr.ib(type=timedelta,
                                      default=ACCESS_TOKEN_EXPIRATION)
    token = attr.ib(type=str,
                    default=attr.Factory(lambda: generate_secret(64)))
    access_tokens = attr.ib(type=list, default=attr.Factory(list), cmp=False)


@attr.s(slots=True)
class AccessToken:
    """Access token to access the API.

    These will only ever be stored in memory and not be persisted.
    """

    refresh_token = attr.ib(type=RefreshToken)
    created_at = attr.ib(type=datetime, default=attr.Factory(dt_util.utcnow))
    token = attr.ib(type=str,
                    default=attr.Factory(generate_secret))

    @property
    def expired(self):
        """Return if this token has expired."""
        expires = self.created_at + self.refresh_token.access_token_expiration
        return dt_util.utcnow() > expires


@attr.s(slots=True)
class Credentials:
    """Credentials for a user on an auth provider."""

    auth_provider_type = attr.ib(type=str)
    auth_provider_id = attr.ib(type=str)

    # Allow the auth provider to store data to represent their auth.
    data = attr.ib(type=dict)

    id = attr.ib(type=str, default=attr.Factory(lambda: uuid.uuid4().hex))
    is_new = attr.ib(type=bool, default=True)


@attr.s(slots=True)
class Client:
    """Client that interacts with Home Assistant on behalf of a user."""

    name = attr.ib(type=str)
    id = attr.ib(type=str, default=attr.Factory(lambda: uuid.uuid4().hex))
    secret = attr.ib(type=str, default=attr.Factory(generate_secret))
    redirect_uris = attr.ib(type=list, default=attr.Factory(list))


async def load_auth_provider_module(hass, provider):
    """Load an auth provider."""
    try:
        module = importlib.import_module(
            'homeassistant.auth_providers.{}'.format(provider))
    except ImportError:
        _LOGGER.warning('Unable to find auth provider %s', provider)
        return None

    if hass.config.skip_pip or not hasattr(module, 'REQUIREMENTS'):
        return module

    processed = hass.data.get(DATA_REQS)

    if processed is None:
        processed = hass.data[DATA_REQS] = set()
    elif provider in processed:
        return module

    req_success = await requirements.async_process_requirements(
        hass, 'auth provider {}'.format(provider), module.REQUIREMENTS)

    if not req_success:
        return None

    return module


async def auth_manager_from_config(hass, provider_configs):
    """Initialize an auth manager from config."""
    store = AuthStore(hass)
    if provider_configs:
        providers = await asyncio.gather(
            *[_auth_provider_from_config(hass, store, config)
              for config in provider_configs])
    else:
        providers = []
    # So returned auth providers are in same order as config
    provider_hash = OrderedDict()
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
    return manager


async def _auth_provider_from_config(hass, store, config):
    """Initialize an auth provider from a config."""
    provider_name = config[CONF_TYPE]
    module = await load_auth_provider_module(hass, provider_name)

    if module is None:
        return None

    try:
        config = module.CONFIG_SCHEMA(config)
    except vol.Invalid as err:
        _LOGGER.error('Invalid configuration for auth provider %s: %s',
                      provider_name, humanize_error(config, err))
        return None

    return AUTH_PROVIDERS[provider_name](hass, store, config)


class AuthManager:
    """Manage the authentication for Home Assistant."""

    def __init__(self, hass, store, providers):
        """Initialize the auth manager."""
        self._store = store
        self._providers = providers
        self.login_flow = data_entry_flow.FlowManager(
            hass, self._async_create_login_flow,
            self._async_finish_login_flow)
        self._access_tokens = {}

    @property
    def active(self):
        """Return if any auth providers are registered."""
        return bool(self._providers)

    @property
    def support_legacy(self):
        """
        Return if legacy_api_password auth providers are registered.

        Should be removed when we removed legacy_api_password auth providers.
        """
        for provider_type, _ in self._providers:
            if provider_type == 'legacy_api_password':
                return True
        return False

    @property
    def async_auth_providers(self):
        """Return a list of available auth providers."""
        return self._providers.values()

    async def async_get_user(self, user_id):
        """Retrieve a user."""
        return await self._store.async_get_user(user_id)

    async def async_get_or_create_user(self, credentials):
        """Get or create a user."""
        return await self._store.async_get_or_create_user(
            credentials, self._async_get_auth_provider(credentials))

    async def async_link_user(self, user, credentials):
        """Link credentials to an existing user."""
        await self._store.async_link_user(user, credentials)

    async def async_remove_user(self, user):
        """Remove a user."""
        await self._store.async_remove_user(user)

    async def async_create_refresh_token(self, user, client_id):
        """Create a new refresh token for a user."""
        return await self._store.async_create_refresh_token(user, client_id)

    async def async_get_refresh_token(self, token):
        """Get refresh token by token."""
        return await self._store.async_get_refresh_token(token)

    @callback
    def async_create_access_token(self, refresh_token):
        """Create a new access token."""
        access_token = AccessToken(refresh_token)
        self._access_tokens[access_token.token] = access_token
        return access_token

    @callback
    def async_get_access_token(self, token):
        """Get an access token."""
        tkn = self._access_tokens.get(token)

        if tkn is None:
            return None

        if tkn.expired:
            self._access_tokens.pop(token)
            return None

        return tkn

    async def async_create_client(self, name, *, redirect_uris=None,
                                  no_secret=False):
        """Create a new client."""
        return await self._store.async_create_client(
            name, redirect_uris, no_secret)

    async def async_get_or_create_client(self, name, *, redirect_uris=None,
                                         no_secret=False):
        """Find a client, if not exists, create a new one."""
        for client in await self._store.async_get_clients():
            if client.name == name:
                return client

        return await self._store.async_create_client(
            name, redirect_uris, no_secret)

    async def async_get_client(self, client_id):
        """Get a client."""
        return await self._store.async_get_client(client_id)

    async def _async_create_login_flow(self, handler, *, source, data):
        """Create a login flow."""
        auth_provider = self._providers[handler]

        if not auth_provider.initialized:
            auth_provider.initialized = True
            await auth_provider.async_initialize()

        return await auth_provider.async_credential_flow()

    async def _async_finish_login_flow(self, result):
        """Result of a credential login flow."""
        if result['type'] != data_entry_flow.RESULT_TYPE_CREATE_ENTRY:
            return None

        auth_provider = self._providers[result['handler']]
        return await auth_provider.async_get_or_create_credentials(
            result['data'])

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

    def __init__(self, hass):
        """Initialize the auth store."""
        self.hass = hass
        self._users = None
        self._clients = None
        self._store = hass.helpers.storage.Store(STORAGE_VERSION, STORAGE_KEY)

    async def credentials_for_provider(self, provider_type, provider_id):
        """Return credentials for specific auth provider type and id."""
        if self._users is None:
            await self.async_load()

        return [
            credentials
            for user in self._users.values()
            for credentials in user.credentials
            if (credentials.auth_provider_type == provider_type and
                credentials.auth_provider_id == provider_id)
        ]

    async def async_get_users(self):
        """Retrieve all users."""
        if self._users is None:
            await self.async_load()

        return list(self._users.values())

    async def async_get_user(self, user_id):
        """Retrieve a user."""
        if self._users is None:
            await self.async_load()

        return self._users.get(user_id)

    async def async_get_or_create_user(self, credentials, auth_provider):
        """Get or create a new user for given credentials.

        If link_user is passed in, the credentials will be linked to the passed
        in user if the credentials are new.
        """
        if self._users is None:
            await self.async_load()

        # New credentials, store in user
        if credentials.is_new:
            info = await auth_provider.async_user_meta_for_credentials(
                credentials)
            # Make owner and activate user if it's the first user.
            if self._users:
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
            self._users[new_user.id] = new_user
            await self.async_link_user(new_user, credentials)
            return new_user

        for user in self._users.values():
            for creds in user.credentials:
                if (creds.auth_provider_type == credentials.auth_provider_type
                        and creds.auth_provider_id ==
                        credentials.auth_provider_id):
                    return user

        raise ValueError('We got credentials with ID but found no user')

    async def async_link_user(self, user, credentials):
        """Add credentials to an existing user."""
        user.credentials.append(credentials)
        await self.async_save()
        credentials.is_new = False

    async def async_remove_user(self, user):
        """Remove a user."""
        self._users.pop(user.id)
        await self.async_save()

    async def async_create_refresh_token(self, user, client_id):
        """Create a new token for a user."""
        local_user = await self.async_get_user(user.id)
        if local_user is None:
            raise ValueError('Invalid user')

        local_client = await self.async_get_client(client_id)
        if local_client is None:
            raise ValueError('Invalid client_id')

        refresh_token = RefreshToken(user, client_id)
        user.refresh_tokens[refresh_token.token] = refresh_token
        await self.async_save()
        return refresh_token

    async def async_get_refresh_token(self, token):
        """Get refresh token by token."""
        if self._users is None:
            await self.async_load()

        for user in self._users.values():
            refresh_token = user.refresh_tokens.get(token)
            if refresh_token is not None:
                return refresh_token

        return None

    async def async_create_client(self, name, redirect_uris, no_secret):
        """Create a new client."""
        if self._clients is None:
            await self.async_load()

        kwargs = {
            'name': name,
            'redirect_uris': redirect_uris
        }

        if no_secret:
            kwargs['secret'] = None

        client = Client(**kwargs)
        self._clients[client.id] = client
        await self.async_save()
        return client

    async def async_get_clients(self):
        """Return all clients."""
        if self._clients is None:
            await self.async_load()

        return list(self._clients.values())

    async def async_get_client(self, client_id):
        """Get a client."""
        if self._clients is None:
            await self.async_load()

        return self._clients.get(client_id)

    async def async_load(self):
        """Load the users."""
        data = await self._store.async_load()

        # Make sure that we're not overriding data if 2 loads happened at the
        # same time
        if self._users is not None:
            return

        if data is None:
            self._users = {}
            self._clients = {}
            return

        users = {
            user_dict['id']: User(**user_dict) for user_dict in data['users']
        }

        for cred_dict in data['credentials']:
            users[cred_dict['user_id']].credentials.append(Credentials(
                id=cred_dict['id'],
                is_new=False,
                auth_provider_type=cred_dict['auth_provider_type'],
                auth_provider_id=cred_dict['auth_provider_id'],
                data=cred_dict['data'],
            ))

        refresh_tokens = {}

        for rt_dict in data['refresh_tokens']:
            token = RefreshToken(
                id=rt_dict['id'],
                user=users[rt_dict['user_id']],
                client_id=rt_dict['client_id'],
                created_at=dt_util.parse_datetime(rt_dict['created_at']),
                access_token_expiration=timedelta(
                    seconds=rt_dict['access_token_expiration']),
                token=rt_dict['token'],
            )
            refresh_tokens[token.id] = token
            users[rt_dict['user_id']].refresh_tokens[token.token] = token

        for ac_dict in data['access_tokens']:
            refresh_token = refresh_tokens[ac_dict['refresh_token_id']]
            token = AccessToken(
                refresh_token=refresh_token,
                created_at=dt_util.parse_datetime(ac_dict['created_at']),
                token=ac_dict['token'],
            )
            refresh_token.access_tokens.append(token)

        clients = {
            cl_dict['id']: Client(**cl_dict) for cl_dict in data['clients']
        }

        self._users = users
        self._clients = clients

    async def async_save(self):
        """Save users."""
        users = [
            {
                'id': user.id,
                'is_owner': user.is_owner,
                'is_active': user.is_active,
                'name': user.name,
            }
            for user in self._users.values()
        ]

        credentials = [
            {
                'id': credential.id,
                'user_id': user.id,
                'auth_provider_type': credential.auth_provider_type,
                'auth_provider_id': credential.auth_provider_id,
                'data': credential.data,
            }
            for user in self._users.values()
            for credential in user.credentials
        ]

        refresh_tokens = [
            {
                'id': refresh_token.id,
                'user_id': user.id,
                'client_id': refresh_token.client_id,
                'created_at': refresh_token.created_at.isoformat(),
                'access_token_expiration':
                    refresh_token.access_token_expiration.total_seconds(),
                'token': refresh_token.token,
            }
            for user in self._users.values()
            for refresh_token in user.refresh_tokens.values()
        ]

        access_tokens = [
            {
                'id': user.id,
                'refresh_token_id': refresh_token.id,
                'created_at': access_token.created_at.isoformat(),
                'token': access_token.token,
            }
            for user in self._users.values()
            for refresh_token in user.refresh_tokens.values()
            for access_token in refresh_token.access_tokens
        ]

        clients = [
            {
                'id': client.id,
                'name': client.name,
                'secret': client.secret,
                'redirect_uris': client.redirect_uris,
            }
            for client in self._clients.values()
        ]

        data = {
            'users': users,
            'clients': clients,
            'credentials': credentials,
            'access_tokens': access_tokens,
            'refresh_tokens': refresh_tokens,
        }

        await self._store.async_save(data, delay=1)
