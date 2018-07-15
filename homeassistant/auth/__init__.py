"""Provide an authentication layer for Home Assistant."""
import asyncio
import logging
from collections import OrderedDict

from homeassistant import data_entry_flow
from homeassistant.core import callback

from . import auth_store
from . import models
from .mfa_modules import auth_mfa_module_from_config
from .providers import auth_provider_from_config

_LOGGER = logging.getLogger(__name__)


async def auth_manager_from_config(hass, provider_configs, module_configs):
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

    if module_configs:
        modules = await asyncio.gather(
            *[auth_mfa_module_from_config(hass, config)
              for config in module_configs])
    else:
        modules = []
    # So returned auth modules are in same order as config
    module_hash = OrderedDict()
    for module in modules:
        if module is None:
            continue

        if module.id in module_hash:
            _LOGGER.error(
                'Found duplicate multi-factor module: %s. Please add unique '
                'IDs if you want to have the same module twice.', module.id)
            continue

        module_hash[module.id] = module

    manager = AuthManager(hass, store, provider_hash, module_hash)
    return manager


class AuthManager:
    """Manage the authentication for Home Assistant."""

    def __init__(self, hass, store, providers, mfa_modules):
        """Initialize the auth manager."""
        self.hass = hass
        self._store = store
        self._providers = providers
        self._mfa_modules = mfa_modules
        self.login_flow = data_entry_flow.FlowManager(
            hass, self._async_create_login_flow,
            self._async_finish_login_flow)
        self._access_tokens = OrderedDict()

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

    @property
    def auth_mfa_modules(self):
        """Return a list of available auth modules."""
        return list(self._mfa_modules.values())

    def get_auth_mfa_module(self, module_id):
        """Return an multi-factor auth module, None if not found."""
        return self._mfa_modules.get(module_id)

    async def async_get_users(self):
        """Retrieve all users."""
        return await self._store.async_get_users()

    async def async_get_user(self, user_id):
        """Retrieve a user."""
        return await self._store.async_get_user(user_id)

    async def async_get_user_by_credentials(self, credentials):
        """Get a user by credential, raise ValueError if not found."""
        for user in await self.async_get_users():
            for creds in user.credentials:
                if creds.id == credentials.id:
                    return user

        return None

    async def async_create_system_user(self, name):
        """Create a system user."""
        return await self._store.async_create_user(
            name=name,
            system_generated=True,
            is_active=True,
        )

    async def async_create_user(self, name):
        """Create a user."""
        return await self._store.async_create_user(
            name=name,
            is_active=True,
        )

    async def async_get_or_create_user(self, credentials):
        """Get or create a user."""
        if not credentials.is_new:
            return await self.async_get_user_by_credentials(credentials)

        auth_provider = self._async_get_auth_provider(credentials)

        if auth_provider is None:
            raise RuntimeError('Credential with unknown provider encountered')

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
        tasks = [
            self.async_remove_credentials(credentials)
            for credentials in user.credentials
        ]

        if tasks:
            await asyncio.wait(tasks)

        await self._store.async_remove_user(user)

    async def async_remove_credentials(self, credentials):
        """Remove credentials."""
        provider = self._async_get_auth_provider(credentials)

        if (provider is not None and
                hasattr(provider, 'async_will_remove_credentials')):
            await provider.async_will_remove_credentials(credentials)

        await self._store.async_remove_credentials(credentials)

    async def async_enable_user_mfa(self, user, mfa_module_id, data=None):
        """Enable a multi-factor auth module for user."""
        if mfa_module_id not in self._mfa_modules:
            raise ValueError('Unable find multi-factor auth module: {}'
                             .format(mfa_module_id))
        if user.system_generated:
            raise ValueError('System generated users cannot enable '
                             'multi-factor auth module.')

        module = self.get_auth_mfa_module(mfa_module_id)
        result = await module.async_setup_user(user.id, data)
        await self._store.async_enable_user_mfa(user, mfa_module_id)
        return result

    async def async_disable_user_mfa(self, user, mfa_module_id):
        """Disable a multi-factor auth module for user."""
        if mfa_module_id not in self._mfa_modules:
            raise ValueError('Unable find multi-factor auth module: {}'
                             .format(mfa_module_id))
        if user.system_generated:
            raise ValueError('System generated users cannot disable '
                             'multi-factor auth module.')

        module = self.get_auth_mfa_module(mfa_module_id)
        await module.async_depose_user(user.id)
        await self._store.async_disable_user_mfa(user, mfa_module_id)

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

        return await auth_provider.async_login_flow()

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
        return self._providers.get(auth_provider_key)
