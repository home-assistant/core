"""Support Legacy API password auth provider.

It will be removed when auth system production ready
"""

from __future__ import annotations

from collections.abc import Mapping
import hmac
from typing import Any, cast

import voluptuous as vol

from homeassistant.core import async_get_hass, callback
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue

from ..models import AuthFlowResult, Credentials, UserMeta
from . import AUTH_PROVIDER_SCHEMA, AUTH_PROVIDERS, AuthProvider, LoginFlow

AUTH_PROVIDER_TYPE = "legacy_api_password"
CONF_API_PASSWORD = "api_password"

_CONFIG_SCHEMA = AUTH_PROVIDER_SCHEMA.extend(
    {vol.Required(CONF_API_PASSWORD): cv.string}, extra=vol.PREVENT_EXTRA
)


def _create_repair_and_validate(config: dict[str, Any]) -> dict[str, Any]:
    async_create_issue(
        async_get_hass(),
        "auth",
        "deprecated_legacy_api_password",
        breaks_in_ha_version="2024.6.0",
        is_fixable=False,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_legacy_api_password",
    )

    return _CONFIG_SCHEMA(config)  # type: ignore[no-any-return]


CONFIG_SCHEMA = _create_repair_and_validate


LEGACY_USER_NAME = "Legacy API password user"


class InvalidAuthError(HomeAssistantError):
    """Raised when submitting invalid authentication."""


@AUTH_PROVIDERS.register(AUTH_PROVIDER_TYPE)
class LegacyApiPasswordAuthProvider(AuthProvider):
    """An auth provider support legacy api_password."""

    DEFAULT_TITLE = "Legacy API Password"

    @property
    def api_password(self) -> str:
        """Return api_password."""
        return str(self.config[CONF_API_PASSWORD])

    async def async_login_flow(self, context: dict[str, Any] | None) -> LoginFlow:
        """Return a flow to login."""
        return LegacyLoginFlow(self)

    @callback
    def async_validate_login(self, password: str) -> None:
        """Validate password."""
        api_password = str(self.config[CONF_API_PASSWORD])

        if not hmac.compare_digest(
            api_password.encode("utf-8"), password.encode("utf-8")
        ):
            raise InvalidAuthError

    async def async_get_or_create_credentials(
        self, flow_result: Mapping[str, str]
    ) -> Credentials:
        """Return credentials for this login."""
        credentials = await self.async_credentials()
        if credentials:
            return credentials[0]

        return self.async_create_credentials({})

    async def async_user_meta_for_credentials(
        self, credentials: Credentials
    ) -> UserMeta:
        """Return info for the user.

        Will be used to populate info when creating a new user.
        """
        return UserMeta(name=LEGACY_USER_NAME, is_active=True)


class LegacyLoginFlow(LoginFlow):
    """Handler for the login flow."""

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> AuthFlowResult:
        """Handle the step of the form."""
        errors = {}

        if user_input is not None:
            try:
                cast(
                    LegacyApiPasswordAuthProvider, self._auth_provider
                ).async_validate_login(user_input["password"])
            except InvalidAuthError:
                errors["base"] = "invalid_auth"

            if not errors:
                return await self.async_finish({})

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({vol.Required("password"): str}),
            errors=errors,
        )
