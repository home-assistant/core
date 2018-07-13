"""Provide an authentication layer for Home Assistant."""
import asyncio
import logging
from collections import OrderedDict

from homeassistant import data_entry_flow
from homeassistant.core import callback

from . import models
from . import auth_store
from .providers import auth_provider_from_config

_LOGGER = logging.getLogger(__name__)


async def auth_manager_from_config(hass, provider_configs):
    """Initialize an auth manager from config."""
    store = auth_store.AuthStore(hass)
    if provider_configs:
        providers = await asyncio.gather(
            *[auth_provider_from_config(hass, store, config)
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

    async def async_create_system_user(self, name):
        """Create a system user."""
        return await self._store.async_create_user(
            name=name,
            system_generated=True,
            is_active=True,
        )

    async def async_get_or_create_user(self, credentials):
        """Get or create a user."""
        if not credentials.is_new:
            for user in await self._store.async_get_users():
                for creds in user.credentials:
                    if creds.id == credentials.id:
                        return user

            raise ValueError('Unable to find the user.')

        auth_provider = self._async_get_auth_provider(credentials)
        info = await auth_provider.async_user_meta_for_credentials(
            credentials)

        kwargs = {
            'credentials': credentials,
            'name': info.get('name')
        }

        # Make owner and activate user if it's the first user.
        if await self._store.async_get_users():
            kwargs['is_owner'] = False
            kwargs['is_active'] = False
        else:
            kwargs['is_owner'] = True
            kwargs['is_active'] = True

        return await self._store.async_create_user(**kwargs)

    async def async_link_user(self, user, credentials):
        """Link credentials to an existing user."""
        await self._store.async_link_user(user, credentials)

    async def async_remove_user(self, user):
        """Remove a user."""
        await self._store.async_remove_user(user)

    async def async_create_refresh_token(self, user, client_id=None):
        """Create a new refresh token for a user."""
        if not user.is_active:
            raise ValueError('User is not active')

        if user.system_generated and client_id is not None:
            raise ValueError(
                'System generated users cannot have refresh tokens connected '
                'to a client.')

        if not user.system_generated and client_id is None:
            raise ValueError('Client is required to generate a refresh token.')

        return await self._store.async_create_refresh_token(user, client_id)

    async def async_get_refresh_token(self, token):
        """Get refresh token by token."""
        return await self._store.async_get_refresh_token(token)

    @callback
    def async_create_access_token(self, refresh_token):
        """Create a new access token."""
        access_token = models.AccessToken(refresh_token=refresh_token)
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
