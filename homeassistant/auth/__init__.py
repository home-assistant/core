"""Provide an authentication layer for Home Assistant."""
import asyncio
import logging
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Tuple, cast

import jwt

from homeassistant import data_entry_flow
from homeassistant.core import callback, HomeAssistant
from homeassistant.util import dt as dt_util

from . import auth_store, models
from .providers import auth_provider_from_config, AuthProvider

_LOGGER = logging.getLogger(__name__)
_ProviderKey = Tuple[str, Optional[str]]
_ProviderDict = Dict[_ProviderKey, AuthProvider]


async def auth_manager_from_config(
        hass: HomeAssistant,
        provider_configs: List[Dict[str, Any]]) -> 'AuthManager':
    """Initialize an auth manager from config."""
    store = auth_store.AuthStore(hass)
    if provider_configs:
        providers = await asyncio.gather(
            *[auth_provider_from_config(hass, store, config)
              for config in provider_configs])
    else:
        providers = ()
    # So returned auth providers are in same order as config
    provider_hash = OrderedDict()  # type: _ProviderDict
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

    def __init__(self, hass: HomeAssistant, store: auth_store.AuthStore,
                 providers: _ProviderDict) -> None:
        """Initialize the auth manager."""
        self._store = store
        self._providers = providers
        self.login_flow = data_entry_flow.FlowManager(
            hass, self._async_create_login_flow,
            self._async_finish_login_flow)

    @property
    def active(self) -> bool:
        """Return if any auth providers are registered."""
        return bool(self._providers)

    @property
    def support_legacy(self) -> bool:
        """
        Return if legacy_api_password auth providers are registered.

        Should be removed when we removed legacy_api_password auth providers.
        """
        for provider_type, _ in self._providers:
            if provider_type == 'legacy_api_password':
                return True
        return False

    @property
    def auth_providers(self) -> List[AuthProvider]:
        """Return a list of available auth providers."""
        return list(self._providers.values())

    async def async_get_users(self) -> List[models.User]:
        """Retrieve all users."""
        return await self._store.async_get_users()

    async def async_get_user(self, user_id: str) -> Optional[models.User]:
        """Retrieve a user."""
        return await self._store.async_get_user(user_id)

    async def async_create_system_user(self, name: str) -> models.User:
        """Create a system user."""
        return await self._store.async_create_user(
            name=name,
            system_generated=True,
            is_active=True,
        )

    async def async_create_user(self, name: str) -> models.User:
        """Create a user."""
        kwargs = {
            'name': name,
            'is_active': True,
        }  # type: Dict[str, Any]

        if await self._user_should_be_owner():
            kwargs['is_owner'] = True

        return await self._store.async_create_user(**kwargs)

    async def async_get_or_create_user(self, credentials: models.Credentials) \
            -> models.User:
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
            name=info.name,
            is_active=info.is_active,
        )

    async def async_link_user(self, user: models.User,
                              credentials: models.Credentials) -> None:
        """Link credentials to an existing user."""
        await self._store.async_link_user(user, credentials)

    async def async_remove_user(self, user: models.User) -> None:
        """Remove a user."""
        tasks = [
            self.async_remove_credentials(credentials)
            for credentials in user.credentials
        ]

        if tasks:
            await asyncio.wait(tasks)

        await self._store.async_remove_user(user)

    async def async_activate_user(self, user: models.User) -> None:
        """Activate a user."""
        await self._store.async_activate_user(user)

    async def async_deactivate_user(self, user: models.User) -> None:
        """Deactivate a user."""
        if user.is_owner:
            raise ValueError('Unable to deactive the owner')
        await self._store.async_deactivate_user(user)

    async def async_remove_credentials(
            self, credentials: models.Credentials) -> None:
        """Remove credentials."""
        provider = self._async_get_auth_provider(credentials)

        if (provider is not None and
                hasattr(provider, 'async_will_remove_credentials')):
            # https://github.com/python/mypy/issues/1424
            await provider.async_will_remove_credentials(  # type: ignore
                credentials)

        await self._store.async_remove_credentials(credentials)

    async def async_create_refresh_token(self, user: models.User,
                                         client_id: Optional[str] = None) \
            -> models.RefreshToken:
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

    async def async_get_refresh_token(
            self, token_id: str) -> Optional[models.RefreshToken]:
        """Get refresh token by id."""
        return await self._store.async_get_refresh_token(token_id)

    async def async_get_refresh_token_by_token(
            self, token: str) -> Optional[models.RefreshToken]:
        """Get refresh token by token."""
        return await self._store.async_get_refresh_token_by_token(token)

    async def async_remove_refresh_token(self,
                                         refresh_token: models.RefreshToken) \
            -> None:
        """Delete a refresh token."""
        await self._store.async_remove_refresh_token(refresh_token)

    @callback
    def async_create_access_token(self,
                                  refresh_token: models.RefreshToken) -> str:
        """Create a new access token."""
        # pylint: disable=no-self-use
        return jwt.encode({
            'iss': refresh_token.id,
            'iat': dt_util.utcnow(),
            'exp': dt_util.utcnow() + refresh_token.access_token_expiration,
        }, refresh_token.jwt_key, algorithm='HS256').decode()

    async def async_validate_access_token(
            self, token: str) -> Optional[models.RefreshToken]:
        """Return refresh token if an access token is valid."""
        try:
            unverif_claims = jwt.decode(token, verify=False)
        except jwt.InvalidTokenError:
            return None

        refresh_token = await self.async_get_refresh_token(
            cast(str, unverif_claims.get('iss')))

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

        if refresh_token is None or not refresh_token.user.is_active:
            return None

        return refresh_token

    async def _async_create_login_flow(
            self, handler: _ProviderKey, *, context: Optional[Dict],
            data: Optional[Any]) -> data_entry_flow.FlowHandler:
        """Create a login flow."""
        auth_provider = self._providers[handler]

        return await auth_provider.async_credential_flow(context)

    async def _async_finish_login_flow(
            self, flow: data_entry_flow.FlowHandler, result: Dict[str, Any]) \
            -> Dict[str, Any]:
        """Return a user as result of login flow."""
        if result['type'] != data_entry_flow.RESULT_TYPE_CREATE_ENTRY:
            return result

        auth_provider = self._providers[result['handler']]
        credentials = await auth_provider.async_get_or_create_credentials(
            result['data'])

        if flow.context is not None and flow.context.get('credential_only'):
            result['result'] = credentials
            return result

        user = await self.async_get_or_create_user(credentials)
        result['result'] = user
        return result

    @callback
    def _async_get_auth_provider(
            self, credentials: models.Credentials) -> Optional[AuthProvider]:
        """Helper to get auth provider from a set of credentials."""
        auth_provider_key = (credentials.auth_provider_type,
                             credentials.auth_provider_id)
        return self._providers.get(auth_provider_key)

    async def _user_should_be_owner(self) -> bool:
        """Determine if user should be owner.

        A user should be an owner if it is the first non-system user that is
        being created.
        """
        for user in await self._store.async_get_users():
            if not user.system_generated:
                return False

        return True
