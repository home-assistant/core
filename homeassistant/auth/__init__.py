"""Provide an authentication layer for Home Assistant."""
import asyncio
import logging
from collections import OrderedDict
from typing import List, Awaitable

import jwt

from homeassistant import data_entry_flow
from homeassistant.core import callback, HomeAssistant
from homeassistant.util import dt as dt_util

from . import auth_store
from .providers import auth_provider_from_config

_LOGGER = logging.getLogger(__name__)


async def auth_manager_from_config(
        hass: HomeAssistant,
        provider_configs: List[dict]) -> Awaitable['AuthManager']:
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
    def auth_providers(self):
        """Return a list of available auth providers."""
        return list(self._providers.values())

    async def async_get_users(self):
        """Retrieve all users."""
        return await self._store.async_get_users()

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

    async def async_create_user(self, name):
        """Create a user."""
        kwargs = {
            'name': name,
            'is_active': True,
        }

        if await self._user_should_be_owner():
            kwargs['is_owner'] = True

        return await self._store.async_create_user(**kwargs)

    async def async_get_or_create_user(self, credentials):
        """Get or create a user."""
        if not credentials.is_new:
            for user in await self._store.async_get_users():
                for creds in user.credentials:
                    if creds.id == credentials.id:
                        return user

            raise ValueError('Unable to find the user.')

        auth_provider = self._async_get_auth_provider(credentials)

        if auth_provider is None:
            raise RuntimeError('Credential with unknown provider encountered')

        info = await auth_provider.async_user_meta_for_credentials(
            credentials)

        return await self._store.async_create_user(
            credentials=credentials,
            name=info.get('name'),
            is_active=info.get('is_active', False)
        )

    async def async_link_user(self, user, credentials):
        """Link credentials to an existing user."""
        await self._store.async_link_user(user, credentials)

    async def async_remove_user(self, user):
        """Remove a user."""
        tasks = [
            self.async_remove_credentials(credentials)
            for credentials in user.credentials
        ]

        if tasks:
            await asyncio.wait(tasks)

        await self._store.async_remove_user(user)

    async def async_activate_user(self, user):
        """Activate a user."""
        await self._store.async_activate_user(user)

    async def async_deactivate_user(self, user):
        """Deactivate a user."""
        if user.is_owner:
            raise ValueError('Unable to deactive the owner')
        await self._store.async_deactivate_user(user)

    async def async_remove_credentials(self, credentials):
        """Remove credentials."""
        provider = self._async_get_auth_provider(credentials)

        if (provider is not None and
                hasattr(provider, 'async_will_remove_credentials')):
            await provider.async_will_remove_credentials(credentials)

        await self._store.async_remove_credentials(credentials)

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

    async def async_get_refresh_token(self, token_id):
        """Get refresh token by id."""
        return await self._store.async_get_refresh_token(token_id)

    async def async_get_refresh_token_by_token(self, token):
        """Get refresh token by token."""
        return await self._store.async_get_refresh_token_by_token(token)

    @callback
    def async_create_access_token(self, refresh_token):
        """Create a new access token."""
        # pylint: disable=no-self-use
        return jwt.encode({
            'iss': refresh_token.id,
            'iat': dt_util.utcnow(),
            'exp': dt_util.utcnow() + refresh_token.access_token_expiration,
        }, refresh_token.jwt_key, algorithm='HS256').decode()

    async def async_validate_access_token(self, token):
        """Return if an access token is valid."""
        try:
            unverif_claims = jwt.decode(token, verify=False)
        except jwt.InvalidTokenError:
            return None

        refresh_token = await self.async_get_refresh_token(
            unverif_claims.get('iss'))

        if refresh_token is None:
            jwt_key = ''
            issuer = ''
        else:
            jwt_key = refresh_token.jwt_key
            issuer = refresh_token.id

        try:
            jwt.decode(
                token,
                jwt_key,
                leeway=10,
                issuer=issuer,
                algorithms=['HS256']
            )
        except jwt.InvalidTokenError:
            return None

        if not refresh_token.user.is_active:
            return None

        return refresh_token

    async def _async_create_login_flow(self, handler, *, context, data):
        """Create a login flow."""
        auth_provider = self._providers[handler]

        return await auth_provider.async_credential_flow(context)

    async def _async_finish_login_flow(self, context, result):
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
        return self._providers.get(auth_provider_key)

    async def _user_should_be_owner(self):
        """Determine if user should be owner.

        A user should be an owner if it is the first non-system user that is
        being created.
        """
        for user in await self._store.async_get_users():
            if not user.system_generated:
                return False

        return True
