"""Provide an authentication layer for Home Assistant."""
import asyncio
from collections import OrderedDict
from datetime import timedelta
import logging
from typing import Any, Dict, List, Optional, Tuple, cast

import jwt

from homeassistant import data_entry_flow
from homeassistant.auth.const import ACCESS_TOKEN_EXPIRATION
from homeassistant.core import HomeAssistant, callback
from homeassistant.util import dt as dt_util

from . import auth_store, models
from .const import GROUP_ID_ADMIN
from .mfa_modules import MultiFactorAuthModule, auth_mfa_module_from_config
from .providers import AuthProvider, LoginFlow, auth_provider_from_config

EVENT_USER_ADDED = "user_added"
EVENT_USER_REMOVED = "user_removed"

_LOGGER = logging.getLogger(__name__)
_MfaModuleDict = Dict[str, MultiFactorAuthModule]
_ProviderKey = Tuple[str, Optional[str]]
_ProviderDict = Dict[_ProviderKey, AuthProvider]


async def auth_manager_from_config(
    hass: HomeAssistant,
    provider_configs: List[Dict[str, Any]],
    module_configs: List[Dict[str, Any]],
) -> "AuthManager":
    """Initialize an auth manager from config.

    CORE_CONFIG_SCHEMA will make sure do duplicated auth providers or
    mfa modules exist in configs.
    """
    store = auth_store.AuthStore(hass)
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
    return manager


class AuthManagerFlowManager(data_entry_flow.FlowManager):
    """Manage authentication flows."""

    def __init__(self, hass: HomeAssistant, auth_manager: "AuthManager"):
        """Init auth manager flows."""
        super().__init__(hass)
        self.auth_manager = auth_manager

    async def async_create_flow(
        self,
        handler_key: Any,
        *,
        context: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> data_entry_flow.FlowHandler:
        """Create a login flow."""
        auth_provider = self.auth_manager.get_auth_provider(*handler_key)
        if not auth_provider:
            raise KeyError(f"Unknown auth provider {handler_key}")
        return await auth_provider.async_login_flow(context)

    async def async_finish_flow(
        self, flow: data_entry_flow.FlowHandler, result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Return a user as result of login flow."""
        flow = cast(LoginFlow, flow)

        if result["type"] != data_entry_flow.RESULT_TYPE_CREATE_ENTRY:
            return result

        # we got final result
        if isinstance(result["data"], models.User):
            result["result"] = result["data"]
            return result

        auth_provider = self.auth_manager.get_auth_provider(*result["handler"])
        if not auth_provider:
            raise KeyError(f"Unknown auth provider {result['handler']}")

        credentials = await auth_provider.async_get_or_create_credentials(
            result["data"]
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
                    flow.user = user
                    flow.available_mfa_modules = modules
                    return await flow.async_step_select_mfa_module()

        result["result"] = await self.auth_manager.async_get_or_create_user(credentials)
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

    @property
    def auth_providers(self) -> List[AuthProvider]:
        """Return a list of available auth providers."""
        return list(self._providers.values())

    @property
    def auth_mfa_modules(self) -> List[MultiFactorAuthModule]:
        """Return a list of available auth modules."""
        return list(self._mfa_modules.values())

    def get_auth_provider(
        self, provider_type: str, provider_id: str
    ) -> Optional[AuthProvider]:
        """Return an auth provider, None if not found."""
        return self._providers.get((provider_type, provider_id))

    def get_auth_providers(self, provider_type: str) -> List[AuthProvider]:
        """Return a List of auth provider of one type, Empty if not found."""
        return [
            provider
            for (p_type, _), provider in self._providers.items()
            if p_type == provider_type
        ]

    def get_auth_mfa_module(self, module_id: str) -> Optional[MultiFactorAuthModule]:
        """Return a multi-factor auth module, None if not found."""
        return self._mfa_modules.get(module_id)

    async def async_get_users(self) -> List[models.User]:
        """Retrieve all users."""
        return await self._store.async_get_users()

    async def async_get_user(self, user_id: str) -> Optional[models.User]:
        """Retrieve a user."""
        return await self._store.async_get_user(user_id)

    async def async_get_owner(self) -> Optional[models.User]:
        """Retrieve the owner."""
        users = await self.async_get_users()
        return next((user for user in users if user.is_owner), None)

    async def async_get_group(self, group_id: str) -> Optional[models.Group]:
        """Retrieve all groups."""
        return await self._store.async_get_group(group_id)

    async def async_get_user_by_credentials(
        self, credentials: models.Credentials
    ) -> Optional[models.User]:
        """Get a user by credential, return None if not found."""
        for user in await self.async_get_users():
            for creds in user.credentials:
                if creds.id == credentials.id:
                    return user

        return None

    async def async_create_system_user(
        self, name: str, group_ids: Optional[List[str]] = None
    ) -> models.User:
        """Create a system user."""
        user = await self._store.async_create_user(
            name=name, system_generated=True, is_active=True, group_ids=group_ids or []
        )

        self.hass.bus.async_fire(EVENT_USER_ADDED, {"user_id": user.id})

        return user

    async def async_create_user(
        self, name: str, group_ids: Optional[List[str]] = None
    ) -> models.User:
        """Create a user."""
        kwargs: Dict[str, Any] = {
            "name": name,
            "is_active": True,
            "group_ids": group_ids or [],
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
            group_ids=[GROUP_ID_ADMIN],
        )

        self.hass.bus.async_fire(EVENT_USER_ADDED, {"user_id": user.id})

        return user

    async def async_link_user(
        self, user: models.User, credentials: models.Credentials
    ) -> None:
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

        self.hass.bus.async_fire(EVENT_USER_REMOVED, {"user_id": user.id})

    async def async_update_user(
        self,
        user: models.User,
        name: Optional[str] = None,
        group_ids: Optional[List[str]] = None,
    ) -> None:
        """Update a user."""
        kwargs: Dict[str, Any] = {}
        if name is not None:
            kwargs["name"] = name
        if group_ids is not None:
            kwargs["group_ids"] = group_ids
        await self._store.async_update_user(user, **kwargs)

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
            # https://github.com/python/mypy/issues/1424
            await provider.async_will_remove_credentials(credentials)  # type: ignore

        await self._store.async_remove_credentials(credentials)

    async def async_enable_user_mfa(
        self, user: models.User, mfa_module_id: str, data: Any
    ) -> None:
        """Enable a multi-factor auth module for user."""
        if user.system_generated:
            raise ValueError(
                "System generated users cannot enable multi-factor auth module."
            )

        module = self.get_auth_mfa_module(mfa_module_id)
        if module is None:
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

        module = self.get_auth_mfa_module(mfa_module_id)
        if module is None:
            raise ValueError(f"Unable find multi-factor auth module: {mfa_module_id}")

        await module.async_depose_user(user.id)

    async def async_get_enabled_mfa(self, user: models.User) -> Dict[str, str]:
        """List enabled mfa modules for user."""
        modules: Dict[str, str] = OrderedDict()
        for module_id, module in self._mfa_modules.items():
            if await module.async_is_user_setup(user.id):
                modules[module_id] = module.name
        return modules

    async def async_create_refresh_token(
        self,
        user: models.User,
        client_id: Optional[str] = None,
        client_name: Optional[str] = None,
        client_icon: Optional[str] = None,
        token_type: Optional[str] = None,
        access_token_expiration: timedelta = ACCESS_TOKEN_EXPIRATION,
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
        )

    async def async_get_refresh_token(
        self, token_id: str
    ) -> Optional[models.RefreshToken]:
        """Get refresh token by id."""
        return await self._store.async_get_refresh_token(token_id)

    async def async_get_refresh_token_by_token(
        self, token: str
    ) -> Optional[models.RefreshToken]:
        """Get refresh token by token."""
        return await self._store.async_get_refresh_token_by_token(token)

    async def async_remove_refresh_token(
        self, refresh_token: models.RefreshToken
    ) -> None:
        """Delete a refresh token."""
        await self._store.async_remove_refresh_token(refresh_token)

    @callback
    def async_create_access_token(
        self, refresh_token: models.RefreshToken, remote_ip: Optional[str] = None
    ) -> str:
        """Create a new access token."""
        self._store.async_log_refresh_token_usage(refresh_token, remote_ip)

        now = dt_util.utcnow()
        return jwt.encode(
            {
                "iss": refresh_token.id,
                "iat": now,
                "exp": now + refresh_token.access_token_expiration,
            },
            refresh_token.jwt_key,
            algorithm="HS256",
        ).decode()

    async def async_validate_access_token(
        self, token: str
    ) -> Optional[models.RefreshToken]:
        """Return refresh token if an access token is valid."""
        try:
            unverif_claims = jwt.decode(token, verify=False)
        except jwt.InvalidTokenError:
            return None

        refresh_token = await self.async_get_refresh_token(
            cast(str, unverif_claims.get("iss"))
        )

        if refresh_token is None:
            jwt_key = ""
            issuer = ""
        else:
            jwt_key = refresh_token.jwt_key
            issuer = refresh_token.id

        try:
            jwt.decode(token, jwt_key, leeway=10, issuer=issuer, algorithms=["HS256"])
        except jwt.InvalidTokenError:
            return None

        if refresh_token is None or not refresh_token.user.is_active:
            return None

        return refresh_token

    @callback
    def _async_get_auth_provider(
        self, credentials: models.Credentials
    ) -> Optional[AuthProvider]:
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
