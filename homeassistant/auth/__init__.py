"""Provide an authentication layer for Home Assistant."""

from __future__ import annotations

import asyncio
from collections import OrderedDict
from collections.abc import Mapping
from datetime import datetime, timedelta
from functools import partial
import time
from typing import Any, cast

import jwt

from homeassistant import data_entry_flow
from homeassistant.core import (
    CALLBACK_TYPE,
    HassJob,
    HassJobType,
    HomeAssistant,
    callback,
)
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.util import dt as dt_util

from . import auth_store, jwt_wrapper, models
from .const import ACCESS_TOKEN_EXPIRATION, GROUP_ID_ADMIN, REFRESH_TOKEN_EXPIRATION
from .mfa_modules import MultiFactorAuthModule, auth_mfa_module_from_config
from .models import AuthFlowResult
from .providers import AuthProvider, LoginFlow, auth_provider_from_config
from .providers.homeassistant import HassAuthProvider

EVENT_USER_ADDED = "user_added"
EVENT_USER_UPDATED = "user_updated"
EVENT_USER_REMOVED = "user_removed"

type _MfaModuleDict = dict[str, MultiFactorAuthModule]
type _ProviderKey = tuple[str, str | None]
type _ProviderDict = dict[_ProviderKey, AuthProvider]


class InvalidAuthError(Exception):
    """Raised when a authentication error occurs."""


class InvalidProvider(Exception):
    """Authentication provider not found."""


async def auth_manager_from_config(
    hass: HomeAssistant,
    provider_configs: list[dict[str, Any]],
    module_configs: list[dict[str, Any]],
) -> AuthManager:
    """Initialize an auth manager from config.

    CORE_CONFIG_SCHEMA will make sure no duplicated auth providers or
    mfa modules exist in configs.
    """
    store = auth_store.AuthStore(hass)
    await store.async_load()
    if provider_configs:
        providers = await asyncio.gather(
            *(
                auth_provider_from_config(hass, store, config)
                for config in provider_configs
            )
        )
    else:
        providers = []
    # So returned auth providers are in same order as config
    provider_hash: _ProviderDict = OrderedDict()
    for provider in providers:
        key = (provider.type, provider.id)
        provider_hash[key] = provider

        if isinstance(provider, HassAuthProvider):
            # Can be removed in 2026.7 with the legacy mode of homeassistant auth provider
            # We need to initialize the provider to create the repair if needed as otherwise
            # the provider will be initialized on first use, which could be rare as users
            # don't frequently change auth settings
            await provider.async_initialize()

    if module_configs:
        modules = await asyncio.gather(
            *(auth_mfa_module_from_config(hass, config) for config in module_configs)
        )
    else:
        modules = []
    # So returned auth modules are in same order as config
    module_hash: _MfaModuleDict = OrderedDict()
    for module in modules:
        module_hash[module.id] = module

    manager = AuthManager(hass, store, provider_hash, module_hash)
    await manager.async_setup()
    return manager


class AuthManagerFlowManager(
    data_entry_flow.FlowManager[AuthFlowResult, tuple[str, str]]
):
    """Manage authentication flows."""

    _flow_result = AuthFlowResult

    def __init__(self, hass: HomeAssistant, auth_manager: AuthManager) -> None:
        """Init auth manager flows."""
        super().__init__(hass)
        self.auth_manager = auth_manager

    async def async_create_flow(
        self,
        handler_key: tuple[str, str],
        *,
        context: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
    ) -> LoginFlow:
        """Create a login flow."""
        auth_provider = self.auth_manager.get_auth_provider(*handler_key)
        if not auth_provider:
            raise KeyError(f"Unknown auth provider {handler_key}")
        return await auth_provider.async_login_flow(context)

    async def async_finish_flow(
        self,
        flow: data_entry_flow.FlowHandler[AuthFlowResult, tuple[str, str]],
        result: AuthFlowResult,
    ) -> AuthFlowResult:
        """Return a user as result of login flow.

        This method is called when a flow step returns FlowResultType.ABORT or
        FlowResultType.CREATE_ENTRY.
        """
        flow = cast(LoginFlow, flow)

        if result["type"] != data_entry_flow.FlowResultType.CREATE_ENTRY:
            return result

        # we got final result
        if isinstance(result["data"], models.Credentials):
            result["result"] = result["data"]
            return result

        auth_provider = self.auth_manager.get_auth_provider(*result["handler"])
        if not auth_provider:
            raise KeyError(f"Unknown auth provider {result['handler']}")

        credentials = await auth_provider.async_get_or_create_credentials(
            cast(Mapping[str, str], result["data"]),
        )

        if flow.context.get("credential_only"):
            result["result"] = credentials
            return result

        # multi-factor module cannot enabled for new credential
        # which has not linked to a user yet
        if auth_provider.support_mfa and not credentials.is_new:
            user = await self.auth_manager.async_get_user_by_credentials(credentials)
            if user is not None:
                modules = await self.auth_manager.async_get_enabled_mfa(user)

                if modules:
                    flow.credential = credentials
                    flow.user = user
                    flow.available_mfa_modules = modules
                    return await flow.async_step_select_mfa_module()

        result["result"] = credentials
        return result


class AuthManager:
    """Manage the authentication for Home Assistant."""

    def __init__(
        self,
        hass: HomeAssistant,
        store: auth_store.AuthStore,
        providers: _ProviderDict,
        mfa_modules: _MfaModuleDict,
    ) -> None:
        """Initialize the auth manager."""
        self.hass = hass
        self._store = store
        self._providers = providers
        self._mfa_modules = mfa_modules
        self.login_flow = AuthManagerFlowManager(hass, self)
        self._revoke_callbacks: dict[str, set[CALLBACK_TYPE]] = {}
        self._expire_callback: CALLBACK_TYPE | None = None
        self._remove_expired_job = HassJob(
            self._async_remove_expired_refresh_tokens, job_type=HassJobType.Callback
        )

    async def async_setup(self) -> None:
        """Set up the auth manager."""
        hass = self.hass
        hass.async_add_shutdown_job(
            HassJob(
                self._async_cancel_expiration_schedule, job_type=HassJobType.Callback
            )
        )
        self._async_track_next_refresh_token_expiration()

    @property
    def auth_providers(self) -> list[AuthProvider]:
        """Return a list of available auth providers."""
        return list(self._providers.values())

    @property
    def auth_mfa_modules(self) -> list[MultiFactorAuthModule]:
        """Return a list of available auth modules."""
        return list(self._mfa_modules.values())

    def get_auth_provider(
        self, provider_type: str, provider_id: str | None
    ) -> AuthProvider | None:
        """Return an auth provider, None if not found."""
        return self._providers.get((provider_type, provider_id))

    def get_auth_providers(self, provider_type: str) -> list[AuthProvider]:
        """Return a List of auth provider of one type, Empty if not found."""
        return [
            provider
            for (p_type, _), provider in self._providers.items()
            if p_type == provider_type
        ]

    def get_auth_mfa_module(self, module_id: str) -> MultiFactorAuthModule | None:
        """Return a multi-factor auth module, None if not found."""
        return self._mfa_modules.get(module_id)

    async def async_get_users(self) -> list[models.User]:
        """Retrieve all users."""
        return await self._store.async_get_users()

    async def async_get_user(self, user_id: str) -> models.User | None:
        """Retrieve a user."""
        return await self._store.async_get_user(user_id)

    async def async_get_owner(self) -> models.User | None:
        """Retrieve the owner."""
        users = await self.async_get_users()
        return next((user for user in users if user.is_owner), None)

    async def async_get_group(self, group_id: str) -> models.Group | None:
        """Retrieve all groups."""
        return await self._store.async_get_group(group_id)

    async def async_get_user_by_credentials(
        self, credentials: models.Credentials
    ) -> models.User | None:
        """Get a user by credential, return None if not found."""
        for user in await self.async_get_users():
            for creds in user.credentials:
                if creds.id == credentials.id:
                    return user

        return None

    async def async_create_system_user(
        self,
        name: str,
        *,
        group_ids: list[str] | None = None,
        local_only: bool | None = None,
    ) -> models.User:
        """Create a system user."""
        user = await self._store.async_create_user(
            name=name,
            system_generated=True,
            is_active=True,
            group_ids=group_ids or [],
            local_only=local_only,
        )

        self.hass.bus.async_fire(EVENT_USER_ADDED, {"user_id": user.id})

        return user

    async def async_create_user(
        self,
        name: str,
        *,
        group_ids: list[str] | None = None,
        local_only: bool | None = None,
    ) -> models.User:
        """Create a user."""
        kwargs: dict[str, Any] = {
            "name": name,
            "is_active": True,
            "group_ids": group_ids or [],
            "local_only": local_only,
        }

        if await self._user_should_be_owner():
            kwargs["is_owner"] = True

        user = await self._store.async_create_user(**kwargs)

        self.hass.bus.async_fire(EVENT_USER_ADDED, {"user_id": user.id})

        return user

    async def async_get_or_create_user(
        self, credentials: models.Credentials
    ) -> models.User:
        """Get or create a user."""
        if not credentials.is_new:
            user = await self.async_get_user_by_credentials(credentials)
            if user is None:
                raise ValueError("Unable to find the user.")
            return user

        auth_provider = self._async_get_auth_provider(credentials)

        if auth_provider is None:
            raise RuntimeError("Credential with unknown provider encountered")

        info = await auth_provider.async_user_meta_for_credentials(credentials)

        user = await self._store.async_create_user(
            credentials=credentials,
            name=info.name,
            is_active=info.is_active,
            group_ids=[GROUP_ID_ADMIN if info.group is None else info.group],
            local_only=info.local_only,
        )

        self.hass.bus.async_fire(EVENT_USER_ADDED, {"user_id": user.id})

        return user

    async def async_link_user(
        self, user: models.User, credentials: models.Credentials
    ) -> None:
        """Link credentials to an existing user."""
        linked_user = await self.async_get_user_by_credentials(credentials)
        if linked_user == user:
            return
        if linked_user is not None:
            raise ValueError("Credential is already linked to a user")

        await self._store.async_link_user(user, credentials)

    async def async_remove_user(self, user: models.User) -> None:
        """Remove a user."""
        tasks = [
            self.async_remove_credentials(credentials)
            for credentials in user.credentials
        ]

        if tasks:
            await asyncio.gather(*tasks)

        await self._store.async_remove_user(user)

        self.hass.bus.async_fire(EVENT_USER_REMOVED, {"user_id": user.id})

    async def async_update_user(
        self,
        user: models.User,
        name: str | None = None,
        is_active: bool | None = None,
        group_ids: list[str] | None = None,
        local_only: bool | None = None,
    ) -> None:
        """Update a user."""
        kwargs: dict[str, Any] = {
            attr_name: value
            for attr_name, value in (
                ("name", name),
                ("group_ids", group_ids),
                ("local_only", local_only),
            )
            if value is not None
        }
        await self._store.async_update_user(user, **kwargs)

        if is_active is not None:
            if is_active is True:
                await self.async_activate_user(user)
            else:
                await self.async_deactivate_user(user)

        self.hass.bus.async_fire(EVENT_USER_UPDATED, {"user_id": user.id})

    @callback
    def async_update_user_credentials_data(
        self, credentials: models.Credentials, data: dict[str, Any]
    ) -> None:
        """Update credentials data."""
        self._store.async_update_user_credentials_data(credentials, data=data)

    async def async_activate_user(self, user: models.User) -> None:
        """Activate a user."""
        await self._store.async_activate_user(user)

    async def async_deactivate_user(self, user: models.User) -> None:
        """Deactivate a user."""
        if user.is_owner:
            raise ValueError("Unable to deactivate the owner")
        await self._store.async_deactivate_user(user)

    async def async_remove_credentials(self, credentials: models.Credentials) -> None:
        """Remove credentials."""
        provider = self._async_get_auth_provider(credentials)

        if provider is not None and hasattr(provider, "async_will_remove_credentials"):
            await provider.async_will_remove_credentials(credentials)

        await self._store.async_remove_credentials(credentials)

    async def async_enable_user_mfa(
        self, user: models.User, mfa_module_id: str, data: Any
    ) -> None:
        """Enable a multi-factor auth module for user."""
        if user.system_generated:
            raise ValueError(
                "System generated users cannot enable multi-factor auth module."
            )

        if (module := self.get_auth_mfa_module(mfa_module_id)) is None:
            raise ValueError(f"Unable find multi-factor auth module: {mfa_module_id}")

        await module.async_setup_user(user.id, data)

    async def async_disable_user_mfa(
        self, user: models.User, mfa_module_id: str
    ) -> None:
        """Disable a multi-factor auth module for user."""
        if user.system_generated:
            raise ValueError(
                "System generated users cannot disable multi-factor auth module."
            )

        if (module := self.get_auth_mfa_module(mfa_module_id)) is None:
            raise ValueError(f"Unable find multi-factor auth module: {mfa_module_id}")

        await module.async_depose_user(user.id)

    async def async_get_enabled_mfa(self, user: models.User) -> dict[str, str]:
        """List enabled mfa modules for user."""
        modules: dict[str, str] = OrderedDict()
        for module_id, module in self._mfa_modules.items():
            if await module.async_is_user_setup(user.id):
                modules[module_id] = module.name
        return modules

    async def async_create_refresh_token(
        self,
        user: models.User,
        client_id: str | None = None,
        client_name: str | None = None,
        client_icon: str | None = None,
        token_type: str | None = None,
        access_token_expiration: timedelta = ACCESS_TOKEN_EXPIRATION,
        credential: models.Credentials | None = None,
    ) -> models.RefreshToken:
        """Create a new refresh token for a user."""
        if not user.is_active:
            raise ValueError("User is not active")

        if user.system_generated and client_id is not None:
            raise ValueError(
                "System generated users cannot have refresh tokens connected "
                "to a client."
            )

        if token_type is None:
            if user.system_generated:
                token_type = models.TOKEN_TYPE_SYSTEM
            else:
                token_type = models.TOKEN_TYPE_NORMAL

        if token_type is models.TOKEN_TYPE_NORMAL:
            expire_at = time.time() + REFRESH_TOKEN_EXPIRATION
        else:
            expire_at = None

        if user.system_generated != (token_type == models.TOKEN_TYPE_SYSTEM):
            raise ValueError(
                "System generated users can only have system type refresh tokens"
            )

        if token_type == models.TOKEN_TYPE_NORMAL and client_id is None:
            raise ValueError("Client is required to generate a refresh token.")

        if (
            token_type == models.TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN
            and client_name is None
        ):
            raise ValueError("Client_name is required for long-lived access token")

        if token_type == models.TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN:
            for token in user.refresh_tokens.values():
                if (
                    token.client_name == client_name
                    and token.token_type == models.TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN
                ):
                    # Each client_name can only have one
                    # long_lived_access_token type of refresh token
                    raise ValueError(f"{client_name} already exists")

        return await self._store.async_create_refresh_token(
            user,
            client_id,
            client_name,
            client_icon,
            token_type,
            access_token_expiration,
            expire_at,
            credential,
        )

    @callback
    def async_get_refresh_token(self, token_id: str) -> models.RefreshToken | None:
        """Get refresh token by id."""
        return self._store.async_get_refresh_token(token_id)

    @callback
    def async_get_refresh_token_by_token(
        self, token: str
    ) -> models.RefreshToken | None:
        """Get refresh token by token."""
        return self._store.async_get_refresh_token_by_token(token)

    @callback
    def async_remove_refresh_token(self, refresh_token: models.RefreshToken) -> None:
        """Delete a refresh token."""
        self._store.async_remove_refresh_token(refresh_token)

        callbacks = self._revoke_callbacks.pop(refresh_token.id, ())
        for revoke_callback in callbacks:
            revoke_callback()

    @callback
    def async_set_expiry(
        self, refresh_token: models.RefreshToken, *, enable_expiry: bool
    ) -> None:
        """Enable or disable expiry of a refresh token."""
        self._store.async_set_expiry(refresh_token, enable_expiry=enable_expiry)

    @callback
    def _async_remove_expired_refresh_tokens(self, _: datetime | None = None) -> None:
        """Remove expired refresh tokens."""
        now = time.time()
        for token in self._store.async_get_refresh_tokens():
            if (expire_at := token.expire_at) is not None and expire_at <= now:
                self.async_remove_refresh_token(token)
        self._async_track_next_refresh_token_expiration()

    @callback
    def _async_track_next_refresh_token_expiration(self) -> None:
        """Initialise all token expiration scheduled tasks."""
        next_expiration = time.time() + REFRESH_TOKEN_EXPIRATION
        for token in self._store.async_get_refresh_tokens():
            if (
                expire_at := token.expire_at
            ) is not None and expire_at < next_expiration:
                next_expiration = expire_at

        self._expire_callback = async_track_point_in_utc_time(
            self.hass,
            self._remove_expired_job,
            dt_util.utc_from_timestamp(next_expiration),
        )

    @callback
    def _async_cancel_expiration_schedule(self) -> None:
        """Cancel tracking of expired refresh tokens."""
        if self._expire_callback:
            self._expire_callback()
            self._expire_callback = None

    @callback
    def _async_unregister(
        self, callbacks: set[CALLBACK_TYPE], callback_: CALLBACK_TYPE
    ) -> None:
        """Unregister a callback."""
        callbacks.remove(callback_)

    @callback
    def async_register_revoke_token_callback(
        self, refresh_token_id: str, revoke_callback: CALLBACK_TYPE
    ) -> CALLBACK_TYPE:
        """Register a callback to be called when the refresh token id is revoked."""
        if refresh_token_id not in self._revoke_callbacks:
            self._revoke_callbacks[refresh_token_id] = set()

        callbacks = self._revoke_callbacks[refresh_token_id]
        callbacks.add(revoke_callback)
        return partial(self._async_unregister, callbacks, revoke_callback)

    @callback
    def async_create_access_token(
        self, refresh_token: models.RefreshToken, remote_ip: str | None = None
    ) -> str:
        """Create a new access token."""
        self.async_validate_refresh_token(refresh_token, remote_ip)

        self._store.async_log_refresh_token_usage(refresh_token, remote_ip)

        now = int(time.time())
        expire_seconds = int(refresh_token.access_token_expiration.total_seconds())
        return jwt.encode(
            {
                "iss": refresh_token.id,
                "iat": now,
                "exp": now + expire_seconds,
            },
            refresh_token.jwt_key,
            algorithm="HS256",
        )

    @callback
    def _async_resolve_provider(
        self, refresh_token: models.RefreshToken
    ) -> AuthProvider | None:
        """Get the auth provider for the given refresh token.

        Raises an exception if the expected provider is no longer available or return
        None if no provider was expected for this refresh token.
        """
        if refresh_token.credential is None:
            return None

        provider = self.get_auth_provider(
            refresh_token.credential.auth_provider_type,
            refresh_token.credential.auth_provider_id,
        )
        if provider is None:
            raise InvalidProvider(
                f"Auth provider {refresh_token.credential.auth_provider_type},"
                f" {refresh_token.credential.auth_provider_id} not available"
            )
        return provider

    @callback
    def async_validate_refresh_token(
        self, refresh_token: models.RefreshToken, remote_ip: str | None = None
    ) -> None:
        """Validate that a refresh token is usable.

        Will raise InvalidAuthError on errors.
        """
        if provider := self._async_resolve_provider(refresh_token):
            provider.async_validate_refresh_token(refresh_token, remote_ip)

    @callback
    def async_validate_access_token(self, token: str) -> models.RefreshToken | None:
        """Return refresh token if an access token is valid."""
        try:
            unverif_claims = jwt_wrapper.unverified_hs256_token_decode(token)
        except jwt.InvalidTokenError:
            return None

        refresh_token = self.async_get_refresh_token(
            cast(str, unverif_claims.get("iss"))
        )

        if refresh_token is None:
            jwt_key = ""
            issuer = ""
        else:
            jwt_key = refresh_token.jwt_key
            issuer = refresh_token.id

        try:
            jwt_wrapper.verify_and_decode(
                token, jwt_key, leeway=10, issuer=issuer, algorithms=["HS256"]
            )
        except jwt.InvalidTokenError:
            return None

        if refresh_token is None or not refresh_token.user.is_active:
            return None

        return refresh_token

    @callback
    def _async_get_auth_provider(
        self, credentials: models.Credentials
    ) -> AuthProvider | None:
        """Get auth provider from a set of credentials."""
        auth_provider_key = (
            credentials.auth_provider_type,
            credentials.auth_provider_id,
        )
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
