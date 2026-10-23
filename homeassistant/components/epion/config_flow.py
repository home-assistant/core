"""Config flow for Epion."""

from collections.abc import Mapping
import logging
from typing import Any, override

from epion import Epion, EpionAuthenticationError, EpionConnectionError
import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(probatio.Secret(CONF_API_KEY)): str,
    }
)


class EpionConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Epion."""

    VERSION = 1

    async def _async_validate_api_key(
        self, api_key: str
    ) -> tuple[str | None, dict[str, str]]:
        """Validate the API key and return the account ID and errors."""
        api = Epion(api_key)
        try:
            api_data = await self.hass.async_add_executor_job(api.get_current)
        except EpionAuthenticationError:
            return None, {"base": "invalid_auth"}
        except EpionConnectionError:
            _LOGGER.error("Unexpected problem when configuring Epion API")
            return None, {"base": "cannot_connect"}
        return api_data["accountId"], {}

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors: dict[str, str] = {}
        if user_input:
            account_id, errors = await self._async_validate_api_key(
                user_input[CONF_API_KEY]
            )
            if not errors:
                await self.async_set_unique_id(account_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="Epion integration",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle re-authentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm re-authentication."""
        errors: dict[str, str] = {}
        if user_input:
            account_id, errors = await self._async_validate_api_key(
                user_input[CONF_API_KEY]
            )
            if not errors:
                await self.async_set_unique_id(account_id)
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(),
                    data_updates={CONF_API_KEY: user_input[CONF_API_KEY]},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
