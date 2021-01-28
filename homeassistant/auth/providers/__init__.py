"""Auth providers for Home Assistant."""
import importlib
import logging
import types
from typing import Any, Dict, List, Optional

import voluptuous as vol
from voluptuous.humanize import humanize_error

from homeassistant import data_entry_flow, requirements
from homeassistant.const import CONF_ID, CONF_NAME, CONF_TYPE
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util
from homeassistant.util.decorator import Registry

from ..auth_store import AuthStore
from ..const import MFA_SESSION_EXPIRATION
from ..models import Credentials, RefreshToken, User, UserMeta

_LOGGER = logging.getLogger(__name__)
DATA_REQS = "auth_prov_reqs_processed"

AUTH_PROVIDERS = Registry()

AUTH_PROVIDER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TYPE): str,
        vol.Optional(CONF_NAME): str,
        # Specify ID if you have two auth providers for same type.
        vol.Optional(CONF_ID): str,
    },
    extra=vol.ALLOW_EXTRA,
)


class AuthProvider:
    """Provider of user authentication."""

    DEFAULT_TITLE = "Unnamed auth provider"

    def __init__(
        self, hass: HomeAssistant, store: AuthStore, config: Dict[str, Any]
    ) -> None:
        """Initialize an auth provider."""
        self.hass = hass
        self.store = store
        self.config = config

    @property
    def id(self) -> Optional[str]:
        """Return id of the auth provider.

        Optional, can be None.
        """
        return self.config.get(CONF_ID)

    @property
    def type(self) -> str:
        """Return type of the provider."""
        return self.config[CONF_TYPE]  # type: ignore

    @property
    def name(self) -> str:
        """Return the name of the auth provider."""
        return self.config.get(CONF_NAME, self.DEFAULT_TITLE)

    @property
    def support_mfa(self) -> bool:
        """Return whether multi-factor auth supported by the auth provider."""
        return True

    async def async_credentials(self) -> List[Credentials]:
        """Return all credentials of this provider."""
        users = await self.store.async_get_users()
        return [
            credentials
            for user in users
            for credentials in user.credentials
            if (
                credentials.auth_provider_type == self.type
                and credentials.auth_provider_id == self.id
            )
        ]

    @callback
    def async_create_credentials(self, data: Dict[str, str]) -> Credentials:
        """Create credentials."""
        return Credentials(
            auth_provider_type=self.type, auth_provider_id=self.id, data=data
        )

    # Implement by extending class

    async def async_login_flow(self, context: Optional[Dict]) -> "LoginFlow":
        """Return the data flow for logging in with auth provider.

        Auth provider should extend LoginFlow and return an instance.
        """
        raise NotImplementedError

    async def async_get_or_create_credentials(
        self, flow_result: Dict[str, str]
    ) -> Credentials:
        """Get credentials based on the flow result."""
        raise NotImplementedError

    async def async_user_meta_for_credentials(
        self, credentials: Credentials
    ) -> UserMeta:
        """Return extra user metadata for credentials.

        Will be used to populate info when creating a new user.
        """
        raise NotImplementedError

    async def async_initialize(self) -> None:
        """Initialize the auth provider."""

    @callback
    def async_validate_refresh_token(
        self, refresh_token: RefreshToken, remote_ip: Optional[str] = None
    ) -> None:
        """Verify a refresh token is still valid.

        Optional hook for an auth provider to verify validity of a refresh token.
        Should raise InvalidAuthError on errors.
        """


async def auth_provider_from_config(
    hass: HomeAssistant, store: AuthStore, config: Dict[str, Any]
) -> AuthProvider:
    """Initialize an auth provider from a config."""
    provider_name = config[CONF_TYPE]
    module = await load_auth_provider_module(hass, provider_name)

    try:
        config = module.CONFIG_SCHEMA(config)  # type: ignore
    except vol.Invalid as err:
        _LOGGER.error(
            "Invalid configuration for auth provider %s: %s",
            provider_name,
            humanize_error(config, err),
        )
        raise

    return AUTH_PROVIDERS[provider_name](hass, store, config)  # type: ignore


async def load_auth_provider_module(
    hass: HomeAssistant, provider: str
) -> types.ModuleType:
    """Load an auth provider."""
    try:
        module = importlib.import_module(f"homeassistant.auth.providers.{provider}")
    except ImportError as err:
        _LOGGER.error("Unable to load auth provider %s: %s", provider, err)
        raise HomeAssistantError(
            f"Unable to load auth provider {provider}: {err}"
        ) from err

    if hass.config.skip_pip or not hasattr(module, "REQUIREMENTS"):
        return module

    processed = hass.data.get(DATA_REQS)

    if processed is None:
        processed = hass.data[DATA_REQS] = set()
    elif provider in processed:
        return module

    # https://github.com/python/mypy/issues/1424
    reqs = module.REQUIREMENTS  # type: ignore
    await requirements.async_process_requirements(
        hass, f"auth provider {provider}", reqs
    )

    processed.add(provider)
    return module


class LoginFlow(data_entry_flow.FlowHandler):
    """Handler for the login flow."""

    def __init__(self, auth_provider: AuthProvider) -> None:
        """Initialize the login flow."""
        self._auth_provider = auth_provider
        self._auth_module_id: Optional[str] = None
        self._auth_manager = auth_provider.hass.auth
        self.available_mfa_modules: Dict[str, str] = {}
        self.created_at = dt_util.utcnow()
        self.invalid_mfa_times = 0
        self.user: Optional[User] = None
        self.credential: Optional[Credentials] = None

    async def async_step_init(
        self, user_input: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Handle the first step of login flow.

        Return self.async_show_form(step_id='init') if user_input is None.
        Return await self.async_finish(flow_result) if login init step pass.
        """
        raise NotImplementedError

    async def async_step_select_mfa_module(
        self, user_input: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Handle the step of select mfa module."""
        errors = {}

        if user_input is not None:
            auth_module = user_input.get("multi_factor_auth_module")
            if auth_module in self.available_mfa_modules:
                self._auth_module_id = auth_module
                return await self.async_step_mfa()
            errors["base"] = "invalid_auth_module"

        if len(self.available_mfa_modules) == 1:
            self._auth_module_id = list(self.available_mfa_modules)[0]
            return await self.async_step_mfa()

        return self.async_show_form(
            step_id="select_mfa_module",
            data_schema=vol.Schema(
                {"multi_factor_auth_module": vol.In(self.available_mfa_modules)}
            ),
            errors=errors,
        )

    async def async_step_mfa(
        self, user_input: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Handle the step of mfa validation."""
        assert self.credential
        assert self.user

        errors = {}

        assert self._auth_module_id is not None
        auth_module = self._auth_manager.get_auth_mfa_module(self._auth_module_id)
        if auth_module is None:
            # Given an invalid input to async_step_select_mfa_module
            # will show invalid_auth_module error
            return await self.async_step_select_mfa_module(user_input={})

        if user_input is None and hasattr(
            auth_module, "async_initialize_login_mfa_step"
        ):
            try:
                await auth_module.async_initialize_login_mfa_step(  # type: ignore
                    self.user.id
                )
            except HomeAssistantError:
                _LOGGER.exception("Error initializing MFA step")
                return self.async_abort(reason="unknown_error")

        if user_input is not None:
            expires = self.created_at + MFA_SESSION_EXPIRATION
            if dt_util.utcnow() > expires:
                return self.async_abort(reason="login_expired")

            result = await auth_module.async_validate(self.user.id, user_input)
            if not result:
                errors["base"] = "invalid_code"
                self.invalid_mfa_times += 1
                if self.invalid_mfa_times >= auth_module.MAX_RETRY_TIME > 0:
                    return self.async_abort(reason="too_many_retry")

            if not errors:
                return await self.async_finish(self.credential)

        description_placeholders: Dict[str, Optional[str]] = {
            "mfa_module_name": auth_module.name,
            "mfa_module_id": auth_module.id,
        }

        return self.async_show_form(
            step_id="mfa",
            data_schema=auth_module.input_schema,
            description_placeholders=description_placeholders,
            errors=errors,
        )

    async def async_finish(self, flow_result: Any) -> Dict:
        """Handle the pass of login flow."""
        return self.async_create_entry(title=self._auth_provider.name, data=flow_result)
